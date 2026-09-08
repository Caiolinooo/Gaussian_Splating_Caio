"""handle_sfm wiring: GPU→CPU fallback surfaces log artifact and used_gpu metric."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from jobs.handlers import handle_sfm
from jobs.models import JobSpec, new_job_record
from jobs.states import SourceKind

IMAGES_TXT = """# Image list with two lines of data per image:
1 0.1 0.2 0.3 0.4 0.0 1.0 2.0 1 frame_000001.jpg
100 200 1 110 210 2
2 0.2 0.1 0.0 0.9 -1.0 0.5 0.0 1 frame_000002.jpg
50 60 -1
"""


@dataclass
class _FakeResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class _HeadlessColmap:
    """GPU steps abort (no GL context); CPU steps produce a minimal model."""

    def run(self, argv: Any, **_kwargs: Any) -> _FakeResult:
        argv = list(argv)
        for flag in ("--SiftExtraction.use_gpu", "--SiftMatching.use_gpu"):
            if flag in argv and argv[argv.index(flag) + 1] == "1":
                return _FakeResult(1, stderr="Cannot create OpenGL context")
        step = argv[1]
        if step == "mapper":
            out = Path(argv[argv.index("--output_path") + 1]) / "0"
            out.mkdir(parents=True, exist_ok=True)
            (out / "images.bin").write_bytes(b"bin")
        if step == "model_converter":
            out = Path(argv[argv.index("--output_path") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / "images.txt").write_text(IMAGES_TXT, encoding="utf-8")
        return _FakeResult(0, stdout=f"{step} ok")


def test_handle_sfm_falls_back_to_cpu_and_exposes_log(tmp_path: Path) -> None:
    record = new_job_record(
        JobSpec(
            user_id="user-a",
            source_kind=SourceKind.IMAGES,
            source_paths=(tmp_path / "a.jpg",),
            user_height_m=1.75,
            work_root=tmp_path / "work",
        )
    )
    record.colmap = replace(record.colmap, min_registered_count=2, min_registered_ratio=0.5)

    frames = Path(record.work_dir) / "frames" / "kept"
    frames.mkdir(parents=True)
    (frames / "frame_000001.jpg").write_bytes(b"x")
    (frames / "frame_000002.jpg").write_bytes(b"x")

    messages: list[str] = []
    outcome = handle_sfm(record, lambda _fraction, message: messages.append(message), _HeadlessColmap())

    assert outcome.metrics["registered"] == 2
    assert outcome.metrics["used_gpu"] is False
    log_path = Path(outcome.artifacts["log"])
    assert log_path.is_file()
    log_text = log_path.read_text(encoding="utf-8")
    assert "Cannot create OpenGL context" in log_text
    assert "use_gpu=0" in log_text
    assert any("CPU" in message for message in messages)
