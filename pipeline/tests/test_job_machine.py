"""State machine: transitions, resume after kill, idempotency, persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from jobs.errors import InvalidTransition, JobInterrupted
from jobs.handlers import StageHandlers, StageOutcome
from jobs.machine import JobMachine, apply_transition, classify_stage_error, resume_stage
from jobs.models import JobSpec, new_job_record
from jobs.states import STAGE_ORDER, JobState, SourceKind, StageStatus, can_transition
from jobs.store import JsonJobStore, SqliteJobStore, record_from_dict, record_to_dict


def _spec(tmp_path: Path, key: str | None = "k1") -> JobSpec:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"fake")
    return JobSpec(
        user_id="user-a",
        source_kind=SourceKind.VIDEO,
        source_paths=(src,),
        user_height_m=1.75,
        work_root=tmp_path / "work",
        idempotency_key=key,
    )


def _ok(name: str) -> object:
    def handler(record: object, progress: object) -> StageOutcome:
        progress(1.0, name)  # type: ignore[operator]
        return StageOutcome(artifacts={name: "ok"}, metrics={"n": 1}, message=name)

    return handler


def _handlers(**overrides: object) -> StageHandlers:
    mapping = {name: _ok(name) for name in STAGE_ORDER}
    mapping.update(overrides)  # type: ignore[arg-type]
    return StageHandlers(
        extract=mapping["extracting"],  # type: ignore[arg-type]
        sfm=mapping["sfm"],  # type: ignore[arg-type]
        training=mapping["training"],  # type: ignore[arg-type]
        exporting=mapping["exporting"],  # type: ignore[arg-type]
        meshproxy=mapping["meshproxy"],  # type: ignore[arg-type]
        autocal=mapping["autocal"],  # type: ignore[arg-type]
    )


def test_legal_and_illegal_transitions() -> None:
    assert can_transition(JobState.QUEUED, JobState.EXTRACTING)
    assert can_transition(JobState.EXTRACTING, JobState.SFM)
    assert can_transition(JobState.SFM, JobState.TRAINING)
    assert can_transition(JobState.TRAINING, JobState.EXPORTING)
    assert can_transition(JobState.EXPORTING, JobState.MESHPROXY)
    assert can_transition(JobState.MESHPROXY, JobState.AUTOCAL)
    assert can_transition(JobState.AUTOCAL, JobState.DONE)
    assert not can_transition(JobState.EXPORTING, JobState.AUTOCAL)
    assert can_transition(JobState.TRAINING, JobState.ERROR)
    assert can_transition(JobState.ERROR, JobState.TRAINING)
    assert not can_transition(JobState.QUEUED, JobState.TRAINING)
    assert not can_transition(JobState.DONE, JobState.EXTRACTING)


def test_apply_transition_rejects_illegal() -> None:
    record = new_job_record(
        JobSpec(
            user_id="u",
            source_kind=SourceKind.IMAGES,
            source_paths=(Path("a.jpg"),),
            user_height_m=1.7,
            work_root=Path("."),
        )
    )
    with pytest.raises(InvalidTransition):
        apply_transition(record, JobState.TRAINING)


def test_full_run_reaches_done(tmp_path: Path) -> None:
    events: list[str] = []
    store = JsonJobStore(tmp_path / "store")
    machine = JobMachine(store, handlers=_handlers(), progress=lambda ev: events.append(ev.state.value))
    record = machine.create(_spec(tmp_path))
    assert record.state is JobState.QUEUED
    done = machine.run(record.job_id)
    assert done.state is JobState.DONE
    assert done.last_completed_stage == "autocal"
    assert all(done.stages[name].status is StageStatus.DONE for name in STAGE_ORDER)
    assert JobState.DONE.value in events


def test_idempotent_rerun_does_not_reenter_stages(tmp_path: Path) -> None:
    calls = {name: 0 for name in STAGE_ORDER}

    def counting(name: str):
        def handler(record: object, progress: object) -> StageOutcome:
            calls[name] += 1
            return StageOutcome(artifacts={}, metrics={}, message=name)

        return handler

    handlers = StageHandlers(
        extract=counting("extracting"),
        sfm=counting("sfm"),
        training=counting("training"),
        exporting=counting("exporting"),
        meshproxy=counting("meshproxy"),
        autocal=counting("autocal"),
    )
    store = SqliteJobStore(tmp_path / "jobs.sqlite")
    machine = JobMachine(store, handlers=handlers)
    record = machine.create(_spec(tmp_path, key="same"))
    machine.run(record.job_id)
    again = machine.run(record.job_id)
    assert again.state is JobState.DONE
    assert calls == {name: 1 for name in STAGE_ORDER}
    reused = machine.create(_spec(tmp_path, key="same"))
    assert reused.job_id == record.job_id


def test_resume_after_simulated_kill_skips_completed_sfm(tmp_path: Path) -> None:
    calls = {"extracting": 0, "sfm": 0, "training": 0}

    def extract(record: object, progress: object) -> StageOutcome:
        calls["extracting"] += 1
        return StageOutcome(artifacts={"frames": "ok"}, metrics={}, message="extract")

    def sfm(record: object, progress: object) -> StageOutcome:
        calls["sfm"] += 1
        return StageOutcome(artifacts={"sparse": "ok"}, metrics={"registered": 80}, message="sfm")

    def training(record: object, progress: object) -> StageOutcome:
        calls["training"] += 1
        if calls["training"] == 1:
            raise JobInterrupted("simulated worker kill")
        return StageOutcome(artifacts={"ply": "ok"}, metrics={"psnr_val": 26.0}, message="train")

    handlers = StageHandlers(
        extract=extract,
        sfm=sfm,
        training=training,
        exporting=_ok("exporting"),  # type: ignore[arg-type]
        meshproxy=_ok("meshproxy"),  # type: ignore[arg-type]
        autocal=_ok("autocal"),  # type: ignore[arg-type]
    )
    store = JsonJobStore(tmp_path / "store")
    machine = JobMachine(store, handlers=handlers)
    record = machine.create(_spec(tmp_path, key=None))
    with pytest.raises(JobInterrupted):
        machine.run(record.job_id)

    mid = store.load(record.job_id)
    assert mid.state is JobState.TRAINING
    assert mid.stages["sfm"].status is StageStatus.DONE
    assert mid.stages["training"].status is StageStatus.RUNNING
    assert mid.last_completed_stage == "sfm"
    assert resume_stage(mid) == "training"

    machine2 = JobMachine(store, handlers=handlers)
    done = machine2.run(record.job_id)
    assert done.state is JobState.DONE
    assert calls["extracting"] == 1
    assert calls["sfm"] == 1
    assert calls["training"] == 2


def test_sfm_file_not_found_maps_to_colmap_failed(tmp_path: Path) -> None:
    def sfm(_record: object, _progress: object) -> StageOutcome:
        raise FileNotFoundError(2, "The system cannot find the file specified", "colmap")

    handlers = StageHandlers(
        extract=_ok("extracting"),  # type: ignore[arg-type]
        sfm=sfm,
        training=_ok("training"),  # type: ignore[arg-type]
        exporting=_ok("exporting"),  # type: ignore[arg-type]
        meshproxy=_ok("meshproxy"),  # type: ignore[arg-type]
        autocal=_ok("autocal"),  # type: ignore[arg-type]
    )
    store = JsonJobStore(tmp_path / "store")
    machine = JobMachine(store, handlers=handlers)
    record = machine.create(_spec(tmp_path, key=None))
    failed = machine.run(record.job_id)
    assert failed.state is JobState.ERROR
    assert failed.error_code == "COLMAP_FAILED"
    assert "Setup" in (failed.error_message or "")
    assert failed.stages["sfm"].status is StageStatus.FAILED
    assert failed.stages["extracting"].status is StageStatus.DONE


def test_classify_stage_error_preserves_coded_exceptions() -> None:
    exc = RuntimeError("boom")
    exc.user_message = "Falha no treino GPU."  # type: ignore[attr-defined]
    exc.code = "TRAINER_FAILED"  # type: ignore[attr-defined]
    code, message = classify_stage_error("training", exc)
    assert code == "TRAINER_FAILED"
    assert message == "Falha no treino GPU."


def test_error_then_retry_from_failed_stage(tmp_path: Path) -> None:
    boom = {"n": 0}

    def training(record: object, progress: object) -> StageOutcome:
        boom["n"] += 1
        if boom["n"] == 1:
            exc = RuntimeError("cuda oom")
            exc.user_message = "Falha no treino GPU."  # type: ignore[attr-defined]
            exc.code = "TRAINER_FAILED"  # type: ignore[attr-defined]
            raise exc
        return StageOutcome(artifacts={}, metrics={}, message="ok")

    handlers = StageHandlers(
        extract=_ok("extracting"),  # type: ignore[arg-type]
        sfm=_ok("sfm"),  # type: ignore[arg-type]
        training=training,
        exporting=_ok("exporting"),  # type: ignore[arg-type]
        meshproxy=_ok("meshproxy"),  # type: ignore[arg-type]
        autocal=_ok("autocal"),  # type: ignore[arg-type]
    )
    store = JsonJobStore(tmp_path / "store")
    machine = JobMachine(store, handlers=handlers)
    record = machine.create(_spec(tmp_path, key=None))
    failed = machine.run(record.job_id)
    assert failed.state is JobState.ERROR
    assert failed.error_code == "TRAINER_FAILED"
    assert failed.stages["training"].status is StageStatus.FAILED
    assert failed.stages["sfm"].status is StageStatus.DONE

    machine.retry(record.job_id)
    done = machine.run(record.job_id)
    assert done.state is JobState.DONE
    assert boom["n"] == 2


def test_retry_resolves_system_python_and_resumes_training(tmp_path: Path, monkeypatch) -> None:
    venv_py = "/home/caio/gaussian-splating/.venv/bin/python"
    monkeypatch.setattr("jobs.machine.resolve_python_bin", lambda _configured: venv_py)
    store = JsonJobStore(tmp_path / "store")
    machine = JobMachine(store, handlers=_handlers())
    record = machine.create(_spec(tmp_path, key=None))
    record.tools.python = "/usr/bin/python3"
    record.state = JobState.ERROR
    record.last_completed_stage = "sfm"
    record.stages["extracting"].status = StageStatus.DONE
    record.stages["sfm"].status = StageStatus.DONE
    record.stages["training"].status = StageStatus.FAILED
    record.stages["training"].error_code = "TRAINER_FAILED"
    store.save(record)

    retried = machine.retry(record.job_id)
    assert retried.tools.python == venv_py
    assert retried.state is JobState.TRAINING
    assert retried.stages["sfm"].status is StageStatus.DONE
    assert retried.stages["training"].status is StageStatus.PENDING


def test_cancel_queued_and_mid_run(tmp_path: Path) -> None:
    store = JsonJobStore(tmp_path / "store")
    machine = JobMachine(store, handlers=_handlers())
    record = machine.create(_spec(tmp_path, key="c1"))
    cancelled = machine.cancel(record.job_id)
    assert cancelled.state is JobState.CANCELLED

    flag = {"cancel": False}

    def extract(record: object, progress: object) -> StageOutcome:
        flag["cancel"] = True
        return StageOutcome(artifacts={}, metrics={}, message="e")

    machine2 = JobMachine(
        store,
        handlers=StageHandlers(
            extract=extract,
            sfm=_ok("sfm"),  # type: ignore[arg-type]
            training=_ok("training"),  # type: ignore[arg-type]
            exporting=_ok("exporting"),  # type: ignore[arg-type]
            meshproxy=_ok("meshproxy"),  # type: ignore[arg-type]
            autocal=_ok("autocal"),  # type: ignore[arg-type]
        ),
        should_cancel=lambda rec: rec.stages["extracting"].status is StageStatus.DONE,
    )
    record2 = machine2.create(_spec(tmp_path, key="c2"))
    finished = machine2.run(record2.job_id)
    assert finished.state is JobState.CANCELLED
    assert flag["cancel"] is True


def test_old_video_ingest_payload_gets_relaxed_dedup() -> None:
    """Retry of pre-fix jobs kept dedup=4.0; missing relax field must default to 0.5."""
    record = record_from_dict(
        {
            "job_id": "old",
            "user_id": "u",
            "state": "error",
            "source": {"kind": "video", "paths": ["/x.mp4"]},
            "work_dir": "/tmp/old",
            "user_height_m": 1.7,
            "created_at": "2026-09-09T00:00:00+00:00",
            "updated_at": "2026-09-09T00:00:00+00:00",
            "video_ingest": {
                "target_min_frames": 150,
                "target_max_frames": 400,
                "dedup_threshold": 4.0,
            },
        }
    )
    assert record.video_ingest.dedup_threshold == 4.0
    assert record.video_ingest.relaxed_dedup_threshold == 0.5
    assert record.video_ingest.min_keep_frames == 8


def test_json_roundtrip_preserves_schema(tmp_path: Path) -> None:
    store = JsonJobStore(tmp_path / "store")
    machine = JobMachine(store, handlers=_handlers())
    created = machine.create(_spec(tmp_path, key="rt"))
    loaded = store.load(created.job_id)
    assert loaded.schema_version == 1
    assert loaded.user_height_m == 1.75
    clone = record_from_dict(record_to_dict(loaded))
    assert clone.job_id == loaded.job_id
    assert clone.state is JobState.QUEUED
    assert set(clone.stages) == set(STAGE_ORDER)


def test_meshproxy_skipped_still_reaches_done(tmp_path: Path) -> None:
    def skip_meshproxy(record: object, progress: object) -> StageOutcome:
        del record
        progress(1.0, "Open3D ausente")  # type: ignore[operator]
        return StageOutcome(
            artifacts={},
            metrics={"skipped": True, "code": "OPEN3D_UNAVAILABLE"},
            message="Open3D ausente — malha proxy pulada.",
            skipped=True,
        )

    store = JsonJobStore(tmp_path / "store")
    machine = JobMachine(store, handlers=_handlers(meshproxy=skip_meshproxy))
    done = machine.run(machine.create(_spec(tmp_path, key="mp-skip")).job_id)
    assert done.state is JobState.DONE
    assert done.stages["meshproxy"].status is StageStatus.SKIPPED
    assert done.stages["autocal"].status is StageStatus.DONE
