# PSD to Godot

PSD to Godot is a Godot 4.7 editor add-on that turns the leaf layers in a
Photoshop PSD or PSB document into PNG textures and a ready-to-open `Sprite2D`
scene.

## Features

- Select PSD and PSB files from an editor dock.
- Preserve layer positions, visibility, names, and stacking order.

## Requirements

- Godot 4.7 or newer.
- Python 3.10 or newer.
- An internet connection the first time `psd-tools` needs to be installed.

Select **Check / Install** in the dock. If `psd-tools` is missing, the add-on
installs it automatically into a writable per-user dependency folder. It does
not require administrator privileges or modify the Godot project.

You can alternatively install it manually for the selected interpreter:

```bash
python3 -m pip install "psd-tools>=1.10,<2"
```

For additional compositing support, manually install the optional dependencies
with `python3 -m pip install "psd-tools[composite]>=1.10,<2"`. On Windows,
replace `python3` with `python` or the full path to `python.exe`.

## Installation

1. Copy `addons/psd_to_godot` into your Godot project.
2. In Godot, open **Project > Project Settings > Plugins**.
3. Enable **PSD to Godot**.
4. Open the **PSD to Godot** editor dock.
5. Enter the Python executable and select **Check / Install**.

## Usage

1. Choose a PSD or PSB document.
2. Choose a generated-files folder inside `res://`.
3. Select **Import PSD as Scene**.
4. When the import completes, select **Open Imported Scene**.

For `menu.psd` and the default output folder, the add-on creates:

```text
res://art/generated/menu/
├── 000_Background.png
├── 001_Buttons__Play.png
├── layers.json
└── menu.tscn
```

The bundled importer can also be called directly:

```bash
python addons/psd_to_godot/psd_importer.py \
  --project-root . \
  --output-dir art/generated \
  path/to/menu.psd
```

## Limitations

- Layers are rasterized. Text, shape, and smart-object editability is not
  retained in Godot.
- Leaf layers become a flat list of `Sprite2D` nodes. PSD groups are retained in
  filenames and manifest metadata, but do not become Godot nodes.
- Photoshop features unsupported by `psd-tools` may render differently from
  Photoshop. Some layer effects have limited support.
- Python is an external dependency and is not included in the add-on archive.
- Importing is an editor workflow and is not supported in exported games.

## Privacy

The add-on processes documents locally and never uploads artwork. If
`psd-tools` is missing, Python's package installer connects to its configured
package index to download it and its dependencies.

## License

MIT. See [LICENSE](LICENSE).
