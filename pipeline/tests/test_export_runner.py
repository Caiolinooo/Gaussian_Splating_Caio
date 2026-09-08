"""Export stays usable when splat-transform is missing."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from export.config import ExportConfig
from export.runner import run_export


class _MissingTransform:
    def run(self, argv, *, cwd=None, env=None, timeout_s=None):
        del cwd, env, timeout_s
        if argv and "splat-transform" in str(argv[0]):
            raise FileNotFoundError(argv[0])
        dest = Path(argv[-1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"thumb")
        return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_export_keeps_ply_when_ksplat_tool_missing(tmp_path: Path) -> None:
    ply = tmp_path / "src.ply"
    ply.write_text("ply\n", encoding="utf-8")
    export_dir = tmp_path / "export"
    result = run_export(
        ExportConfig(),
        source_ply=ply,
        export_dir=export_dir,
        runner=_MissingTransform(),
        frames_dir=None,
    )
    assert result.master_ply.is_file()
    assert not result.web_ksplat.is_file()


class _NpxWithoutPackage:
    """Resolution fell back to `npx`, but npm cannot find the executable."""

    def run(self, argv, *, cwd=None, env=None, timeout_s=None):
        del cwd, env, timeout_s
        if "ksplat" in " ".join(str(item) for item in argv):
            return SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="npm error code E404\nnpm error could not determine executable to run",
            )
        dest = Path(argv[-1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"thumb")
        return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_export_skips_ksplat_when_npx_cannot_find_package(tmp_path: Path) -> None:
    ply = tmp_path / "src.ply"
    ply.write_text("ply\n", encoding="utf-8")
    export_dir = tmp_path / "export"
    result = run_export(
        ExportConfig(splat_transform_bin="npx"),
        source_ply=ply,
        export_dir=export_dir,
        runner=_NpxWithoutPackage(),
        frames_dir=None,
    )
    assert result.master_ply.is_file()
    assert not result.web_ksplat.is_file()
