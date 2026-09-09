"""Testes do Provisioner — independentes do ambiente da máquina."""

import subprocess

from provisioner.bins import resolve_colmap_bin, resolve_python_bin
from provisioner.detect import Status, detect_colmap
from provisioner.health import CHECKERS, run_all_checks
from provisioner.install import (
    PROVISIONING_PLAN,
    StepStatus,
    install_colmap,
    run_provisioning,
)

EXPECTED_COMPONENTS = {
    "gpu",
    "wsl2",
    "disk",
    "memory",
    "ffmpeg",
    "colmap",
    "python",
    "pytorch",
    "gsplat",
}


def test_health_report_contains_all_components() -> None:
    report = run_all_checks()
    keys = {check.key for check in report.checks}
    assert EXPECTED_COMPONENTS <= keys
    assert len(report.checks) == len(CHECKERS)
    assert report.overall in set(Status)
    assert isinstance(report.ready, bool)
    assert report.generated_at


def test_every_check_has_user_facing_message() -> None:
    report = run_all_checks()
    for check in report.checks:
        assert check.message, f"{check.key} sem mensagem para a UI"
        if check.status in (Status.MISSING, Status.ERROR):
            assert check.fix_hint, f"{check.key} sem ação guiada de correção"


def test_provisioning_never_compiles_or_apts_colmap() -> None:
    logs: list[str] = []
    results = run_provisioning(logs.append)
    by_key = {result.key: result for result in results}

    plan_keys = [step.key for step in PROVISIONING_PLAN]
    assert list(by_key) == plan_keys
    assert by_key["detect"].status is StepStatus.DONE
    assert by_key["colmap"].status in {StepStatus.DONE, StepStatus.SKIPPED}
    assert by_key["ffmpeg"].status in {StepStatus.DONE, StepStatus.SKIPPED}
    assert by_key["python-env"].status in {StepStatus.DONE, StepStatus.SKIPPED, StepStatus.ERROR}
    assert by_key["gsplat"].status in {StepStatus.DONE, StepStatus.SKIPPED, StepStatus.ERROR}
    assert by_key["verify"].status in (StepStatus.DONE, StepStatus.ERROR)

    text = "\n".join(logs).lower()
    assert "sudo -n apt-get install -y colmap" not in text
    assert "cmake --build" not in text
    assert "ninja -c" not in text


def test_install_colmap_only_locates(monkeypatch) -> None:
    logs: list[str] = []
    monkeypatch.setattr("provisioner.install.resolve_colmap_bin", lambda _cfg: None)
    monkeypatch.setattr("provisioner.install.colmap_build_in_progress", lambda: False)
    result = install_colmap(logs.append)
    assert result.status is StepStatus.SKIPPED
    assert all("sudo -n apt-get install -y colmap" not in line.lower() for line in logs)
    assert any("não vou compil" in line.lower() for line in logs)


def test_install_colmap_uses_existing_binary(monkeypatch) -> None:
    logs: list[str] = []
    monkeypatch.setattr(
        "provisioner.install.resolve_colmap_bin",
        lambda _cfg: "/home/caio/colmap/build/src/colmap/exe/colmap",
    )
    result = install_colmap(logs.append)
    assert result.status is StepStatus.DONE
    assert "colmap" in result.message.lower()


def _make_venv_python(root) -> object:
    venv = root / ".venv"
    bindir = venv / "bin"
    bindir.mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    python = bindir / "python"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    python.chmod(0o755)
    return python


def test_resolve_python_prefers_venv_over_system(tmp_path, monkeypatch) -> None:
    venv_python = _make_venv_python(tmp_path)
    monkeypatch.setattr("provisioner.bins._discover_venv_python", lambda: str(venv_python))
    assert resolve_python_bin("python") == str(venv_python)
    assert resolve_python_bin("python3") == str(venv_python)
    assert resolve_python_bin("/usr/bin/python3") == str(venv_python)


def test_resolve_python_keeps_explicit_venv(tmp_path, monkeypatch) -> None:
    venv_python = _make_venv_python(tmp_path)
    monkeypatch.setattr("provisioner.bins._discover_venv_python", lambda: "/other/.venv/bin/python")
    assert resolve_python_bin(str(venv_python)) == str(venv_python)


def test_resolve_python_honors_tool_python_env(tmp_path, monkeypatch) -> None:
    venv_python = _make_venv_python(tmp_path)
    monkeypatch.setenv("TOOL_PYTHON", str(venv_python))
    monkeypatch.setattr("provisioner.bins._discover_venv_python", lambda: None)
    assert resolve_python_bin("/usr/bin/python3") == str(venv_python)


def test_resolve_python_system_only_without_venv(monkeypatch) -> None:
    monkeypatch.delenv("TOOL_PYTHON", raising=False)
    monkeypatch.setattr("provisioner.bins._discover_venv_python", lambda: None)
    monkeypatch.setattr("provisioner.bins.shutil.which", lambda name: "/usr/bin/python3" if name else None)
    resolved = resolve_python_bin("python3")
    assert resolved == "/usr/bin/python3"


def test_resolve_colmap_prefers_existing_path(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "colmap"
    fake.write_text("", encoding="utf-8")
    fake.chmod(0o755)
    found = resolve_colmap_bin(str(fake))
    assert found == str(fake.resolve())


def _fake_completed(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["colmap", "-h"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_detect_colmap_broken_binary_is_error(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "colmap"
    fake.write_text("", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setattr("provisioner.detect.resolve_colmap_bin", lambda _cfg: str(fake))
    monkeypatch.setattr(
        "provisioner.detect._run",
        lambda cmd, **_: _fake_completed(127, stderr="error while loading shared libraries: libGL.so.1"),
    )
    check = detect_colmap()
    assert check.status is Status.ERROR
    assert "falhou" in check.message
    assert check.details["returncode"] == 127
    assert "libGL" in check.details["stderr"]
    assert check.fix_hint


def test_detect_colmap_healthy_binary_is_ok(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "colmap"
    fake.write_text("", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setattr("provisioner.detect.resolve_colmap_bin", lambda _cfg: str(fake))
    monkeypatch.setattr(
        "provisioner.detect._run",
        lambda cmd, **_: _fake_completed(0, stdout="COLMAP 3.11 -- Structure-from-Motion\n"),
    )
    check = detect_colmap()
    assert check.status is Status.OK
    assert check.details["banner"] == "COLMAP 3.11 -- Structure-from-Motion"


def test_disk_and_memory_report_positive_numbers() -> None:
    report = run_all_checks()
    disk = next(check for check in report.checks if check.key == "disk")
    assert disk.details["free_gb"] > 0
    memory = next(check for check in report.checks if check.key == "memory")
    if memory.status is not Status.UNKNOWN:
        assert memory.details["total_gb"] > 0
