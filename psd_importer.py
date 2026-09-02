#!/usr/bin/env python3
"""Render Photoshop layers and assemble them into a Godot Sprite2D scene."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
from pathlib import Path
import re
import site
import subprocess
import sys
import tempfile


PLUGIN_VERSION = "1.0.1"
PSD_TOOLS_REQUIREMENT = "psd-tools>=1.10,<2"
USER_DEPENDENCY_DIR = (
    Path(site.getuserbase())
    / "psd_to_godot"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
)

if str(USER_DEPENDENCY_DIR) not in sys.path:
    sys.path.insert(0, str(USER_DEPENDENCY_DIR))

try:
    from psd_tools import PSDImage
except ImportError:
    PSDImage = None


SUPPORTED_SUFFIXES = {".psd", ".psb"}


def clean_name(name: str | None) -> str:
    """Return a filesystem- and node-name-safe fragment."""
    value = (name or "Layer").strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    value = value.strip("._")
    return value or "Layer"


def gd_string(value: str) -> str:
    """JSON quoting is compatible with the strings used in text scenes."""
    return json.dumps(value, ensure_ascii=False)


def install_psd_tools() -> None:
    """Install psd-tools into a writable, per-user plugin dependency folder."""
    USER_DEPENDENCY_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--upgrade",
        "--target",
        str(USER_DEPENDENCY_DIR),
        PSD_TOOLS_REQUIREMENT,
    ]
    print("psd-tools is missing; installing it automatically…", flush=True)
    print(f"Dependency folder: {USER_DEPENDENCY_DIR}", flush=True)
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.stdout:
        print(result.stdout.rstrip(), flush=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Automatic psd-tools installation failed with exit code "
            f"{result.returncode}. Check the output above and your internet connection."
        )


def require_runtime() -> None:
    global PSDImage

    if sys.version_info < (3, 10):
        raise RuntimeError(
            "Python 3.10 or newer is required; found "
            f"{sys.version.split()[0]}."
        )
    if PSDImage is None:
        install_psd_tools()
        importlib.invalidate_caches()
        try:
            PSDImage = importlib.import_module("psd_tools").PSDImage
        except ImportError as exc:
            raise RuntimeError(
                "psd-tools was installed but could not be imported. "
                f"Dependency folder: {USER_DEPENDENCY_DIR}"
            ) from exc


def print_runtime() -> None:
    require_runtime()
    version = importlib.metadata.version("psd-tools")
    print(f"PSD to Godot {PLUGIN_VERSION}")
    print(f"Python {sys.version.split()[0]}: {sys.executable}")
    print(f"psd-tools {version}")


def walk_layers(group, parents=()):
    """Yield every non-group layer together with its PSD hierarchy."""
    for layer in group:
        layer_name = layer.name or "Layer"
        hierarchy = parents + (layer_name,)
        if layer.is_group():
            yield from walk_layers(layer, hierarchy)
        else:
            yield layer, hierarchy


def ensure_inside_project(path: Path, project_root: Path) -> None:
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(
            f"Output folder must be inside the Godot project: {project_root}"
        ) from exc


def godot_path(path: Path, project_root: Path) -> str:
    return f"res://{path.relative_to(project_root).as_posix()}"


def build_scene(scene_name: str, layers: list[dict]) -> str:
    lines = [f"[gd_scene load_steps={len(layers) + 1} format=3]", ""]

    for index, layer in enumerate(layers, start=1):
        resource_id = str(index)
        layer["resource_id"] = resource_id
        lines.append(
            '[ext_resource type="Texture2D" '
            f'path={gd_string(layer["texture"])} '
            f'id={gd_string(resource_id)}]'
        )

    lines.extend(["", f'[node name={gd_string(scene_name)} type="Node2D"]', ""])

    for index, layer in enumerate(layers):
        node_name = f"{index:03d}_{clean_name(layer['name'])}"
        lines.extend(
            [
                f'[node name={gd_string(node_name)} type="Sprite2D" parent="."]',
                f'position = Vector2({layer["x"]}, {layer["y"]})',
                "centered = false",
                f'texture = ExtResource({gd_string(layer["resource_id"])})',
            ]
        )
        if not layer["visible"]:
            lines.append("visible = false")
        lines.append("")

    return "\n".join(lines)


def write_text_atomic(path: Path, contents: str) -> None:
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(contents, encoding="utf-8")
    temporary_path.replace(path)


def previous_generated_files(manifest_path: Path, project_root: Path) -> set[Path]:
    if not manifest_path.exists():
        return set()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()

    paths = set()
    for layer in manifest.get("layers", []):
        texture = layer.get("texture", "")
        if isinstance(texture, str) and texture.startswith("res://"):
            paths.add((project_root / texture.removeprefix("res://")).resolve())
    return paths


def export_psd(psd_path: Path, project_root: Path, output_root: Path) -> Path:
    require_runtime()
    psd_path = psd_path.expanduser().resolve()
    project_root = project_root.expanduser().resolve()
    output_root = output_root.expanduser()
    if not output_root.is_absolute():
        output_root = project_root / output_root
    output_root = output_root.resolve()

    if not psd_path.is_file():
        raise FileNotFoundError(f"Photoshop document not found: {psd_path}")
    if psd_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("Input must have a .psd or .psb extension.")
    if not project_root.is_dir():
        raise NotADirectoryError(f"Godot project folder not found: {project_root}")
    if not (project_root / "project.godot").is_file():
        raise FileNotFoundError(f"No project.godot found in: {project_root}")
    ensure_inside_project(output_root, project_root)

    scene_name = clean_name(psd_path.stem)
    output_dir = output_root / scene_name
    ensure_inside_project(output_dir, project_root)
    output_root.mkdir(parents=True, exist_ok=True)

    psd = PSDImage.open(psd_path)
    exported_layers: list[dict] = []

    with tempfile.TemporaryDirectory(
        prefix=f".{scene_name}_", dir=output_root
    ) as staging_directory:
        staging_dir = Path(staging_directory)

        for original_index, (layer, hierarchy) in enumerate(walk_layers(psd)):
            left, top, right, bottom = layer.bbox
            width = right - left
            height = bottom - top

            if width <= 0 or height <= 0:
                print(f"Skipping empty layer: {layer.name or 'Layer'}")
                continue

            try:
                image = layer.composite()
            except Exception as exc:  # Keep importing independent layers.
                print(f"Could not render '{layer.name or 'Layer'}': {exc}")
                continue

            if image is None:
                print(f"Skipping non-renderable layer: {layer.name or 'Layer'}")
                continue

            hierarchy_name = "__".join(clean_name(item) for item in hierarchy)
            filename = f"{original_index:03d}_{hierarchy_name}.png"
            image.convert("RGBA").save(staging_dir / filename)

            final_png_path = output_dir / filename
            exported_layers.append(
                {
                    "name": layer.name or "Layer",
                    "hierarchy": list(hierarchy),
                    "texture": godot_path(final_png_path, project_root),
                    "x": left,
                    "y": top,
                    "width": width,
                    "height": height,
                    "visible": bool(layer.is_visible()),
                    "filename": filename,
                }
            )
            print(
                f"Rendered: {layer.name or 'Layer'} at ({left}, {top}) -> {filename}"
            )

        scene_contents = build_scene(scene_name, exported_layers)
        manifest = {
            "plugin_version": PLUGIN_VERSION,
            "source_psd": str(psd_path),
            "scene_name": scene_name,
            "layers": exported_layers,
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "layers.json"
        stale_paths = previous_generated_files(manifest_path, project_root)
        new_paths = {
            (output_dir / layer["filename"]).resolve()
            for layer in exported_layers
        }
        for stale_path in stale_paths - new_paths:
            if stale_path.parent == output_dir and stale_path.suffix.lower() == ".png":
                stale_path.unlink(missing_ok=True)

        for layer in exported_layers:
            (staging_dir / layer["filename"]).replace(
                output_dir / layer["filename"]
            )

        scene_path = output_dir / f"{scene_name}.tscn"
        write_text_atomic(scene_path, scene_contents)
        write_text_atomic(
            manifest_path,
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        )

    print(f"Generated {len(exported_layers)} layers in {output_dir}")
    print(f"SCENE_PATH={godot_path(scene_path, project_root)}")
    return scene_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import PSD/PSB layers into a Godot Sprite2D scene."
    )
    parser.add_argument("psd", nargs="?", type=Path, help="PSD or PSB document")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Godot project folder (default: current folder)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("art/generated"),
        help="Output folder inside the project (default: art/generated)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check Python and psd-tools without importing a document",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.check:
            print_runtime()
            return 0
        if args.psd is None:
            raise ValueError("A PSD or PSB document path is required.")
        export_psd(args.psd, args.project_root, args.output_dir)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
