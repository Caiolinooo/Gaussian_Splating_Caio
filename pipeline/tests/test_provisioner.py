"""Testes do Provisioner — independentes do ambiente da máquina."""

from provisioner.bins import resolve_colmap_bin
from provisioner.detect import Status
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


def test_resolve_colmap_prefers_existing_path(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "colmap"
    fake.write_text("", encoding="utf-8")
    fake.chmod(0o755)
    found = resolve_colmap_bin(str(fake))
    assert found == str(fake.resolve())


def test_disk_and_memory_report_positive_numbers() -> None:
    report = run_all_checks()
    disk = next(check for check in report.checks if check.key == "disk")
    assert disk.details["free_gb"] > 0
    memory = next(check for check in report.checks if check.key == "memory")
    if memory.status is not Status.UNKNOWN:
        assert memory.details["total_gb"] > 0
