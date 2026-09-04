"""Testes básicos do Provisioner (Fase 0) — independentes do ambiente da máquina."""

from provisioner.detect import Status
from provisioner.health import CHECKERS, run_all_checks
from provisioner.install import PROVISIONING_PLAN, StepStatus, run_provisioning

EXPECTED_COMPONENTS = {"gpu", "wsl2", "disk", "memory", "ffmpeg", "colmap", "python"}


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


def test_provisioning_install_steps_are_stubs() -> None:
    logs: list[str] = []
    results = run_provisioning(logs.append)
    by_key = {result.key: result for result in results}

    plan_keys = [step.key for step in PROVISIONING_PLAN]
    assert list(by_key) == plan_keys

    assert by_key["detect"].status is StepStatus.DONE
    for key in ("ffmpeg", "colmap", "python-env", "gsplat"):
        assert by_key[key].status is StepStatus.SKIPPED
    assert by_key["verify"].status in (StepStatus.DONE, StepStatus.ERROR)
    assert any("STUB" in line for line in logs)


def test_disk_and_memory_report_positive_numbers() -> None:
    report = run_all_checks()
    disk = next(check for check in report.checks if check.key == "disk")
    assert disk.details["free_gb"] > 0
    memory = next(check for check in report.checks if check.key == "memory")
    if memory.status is not Status.UNKNOWN:
        assert memory.details["total_gb"] > 0
