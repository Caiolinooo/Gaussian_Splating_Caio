from pathlib import Path

from geom.planes import densify_points3d_txt, fit_planes, write_points3d_txt
from relight.sh_env import build_relight_env, evaluate_sh_rgb, light_direction
from temporal.clusters import build_temporal_scene, interpolate_camera, interpolate_offsets
from train.config import QUALITY_DEFAULT_STEPS, TrainConfig, resolve_eval_train_steps


def test_fit_planes_finds_horizontal_sheet() -> None:
    points = [(float(x), 0.0, float(z)) for x in range(-4, 5) for z in range(-4, 5)]
    planes = fit_planes(points, max_planes=1, min_inliers=10, dist_thresh=0.05)
    assert len(planes) == 1
    assert abs(planes[0].ny) > 0.8


def test_densify_points3d_txt_adds_wall_samples(tmp_path: Path) -> None:
    path = tmp_path / "points3D.txt"
    rows = [
        (index, float(x), 1.0, float(z), 10, 10, 10, 0.1, "")
        for index, (x, z) in enumerate(((i, j) for i in range(8) for j in range(8)), start=1)
    ]
    write_points3d_txt(path, rows)
    stats = densify_points3d_txt(path, samples_per_plane=20, max_planes=1)
    assert stats["added"] >= 20
    text = path.read_text(encoding="utf-8")
    assert text.count("\n") > 20


def test_temporal_from_colmap_images(tmp_path: Path) -> None:
    images = tmp_path / "images.txt"
    images.write_text(
        "# IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME\n"
        "1 1 0 0 0 0 0 2 1 frame_000.jpg\n"
        "\n"
        "2 1 0 0 0 0 0 4 1 frame_001.jpg\n"
        "\n",
        encoding="utf-8",
    )
    scene = build_temporal_scene(
        points3d_txt=None,
        images_txt=images,
        frame_count=2,
        duration_s=1.0,
        fps=2.0,
        source_kind="video",
    )
    assert scene.enabled is True
    assert len(scene.cameras) == 2
    mid = interpolate_camera(list(scene.cameras), 0.5)
    assert mid is not None
    assert mid["position"][2] != scene.cameras[0]["position"][2]


def test_interpolate_offsets_lerps() -> None:
    times = [0.0, 1.0]
    keys = [{"t": [0.0, 0.0, 0.0]}, {"t": [2.0, 0.0, 0.0]}]
    x, y, z = interpolate_offsets(times, keys, 0.5)
    assert x == 1.0 and y == 0.0 and z == 0.0


def test_flow_rigs_keys_shift_when_square_moves(tmp_path: Path) -> None:
    from geom.planes import Plane
    from temporal.flow_rigs import estimate_cluster_keys, write_4dgs_npz

    def write_pgm(path: Path, ox: int) -> None:
        width, height = 64, 48
        rows = []
        for y in range(height):
            row = []
            for x in range(width):
                row.append(220 if ox <= x < ox + 10 and 18 <= y < 30 else 20)
            rows.append(row)
        body = "\n".join(" ".join(str(v) for v in row) for row in rows)
        path.write_text(f"P2\n{width} {height}\n255\n{body}\n", encoding="ascii")

    write_pgm(tmp_path / "frame_000.pgm", 8)
    write_pgm(tmp_path / "frame_001.pgm", 20)
    cameras = [
        {"name": "frame_000.pgm", "t": 0.0, "position": [0.0, 0.0, 4.0], "target": [0.0, 0.0, 0.0]},
        {"name": "frame_001.pgm", "t": 1.0, "position": [0.0, 0.0, 4.0], "target": [0.0, 0.0, 0.0]},
    ]
    plane = Plane(0.0, 0.0, 1.0, 0.0, tuple((float(x), 0.0, 0.0) for x in range(-2, 3)))
    keys = estimate_cluster_keys(
        planes=[plane],
        cameras=cameras,
        times=[0.0, 1.0],
        frames_dir=tmp_path,
    )
    assert keys
    moved = keys[0][-1]["t"]
    assert abs(moved[0]) + abs(moved[1]) + abs(moved[2]) > 0
    write_4dgs_npz(tmp_path / "4dgs.npz", [0.0, 1.0], [[item["t"] for item in keys[0]]])
    assert (tmp_path / "4dgs.npz").is_file() or (tmp_path / "4dgs.json").is_file()


def test_relight_changes_rgb_with_direction() -> None:
    env = build_relight_env(sh_degree=3)
    assert env.mode == "sh-env"
    assert env.enabled is True
    up = evaluate_sh_rgb(light_direction(0, 80), 1.4)
    side = evaluate_sh_rgb(light_direction(180, 5), 0.4)
    assert up[1] != side[1]


def test_train_defaults_are_quality_not_eval_fast() -> None:
    cfg = TrainConfig()
    assert cfg.data_factor == 2
    assert cfg.max_steps == QUALITY_DEFAULT_STEPS == 30_000
    assert "--sh_degree" in cfg.extra_args
    assert "3" in cfg.extra_args
    assert "--scale_reg" in cfg.extra_args
    assert resolve_eval_train_steps(40) == 15_000
    assert resolve_eval_train_steps(150) == 30_000
    assert resolve_eval_train_steps(400) == 30_000
    assert resolve_eval_train_steps(40, 12_000) == 12_000
