@tool
extends EditorPlugin

const ImportDock := preload("psd_import_dock.gd")

var _dock: EditorDock
var _content: Control


func _enter_tree() -> void:
	_content = ImportDock.new()
	_content.setup(get_editor_interface())

	_dock = EditorDock.new()
	_dock.name = "PSDToGodotDock"
	_dock.title = "PSD to Godot"
	_dock.layout_key = "psd_to_godot"
	_dock.default_slot = EditorDock.DOCK_SLOT_RIGHT_BL
	_dock.icon_name = &"ImageTexture"
	_dock.add_child(_content)
	add_dock(_dock)


func _exit_tree() -> void:
	if is_instance_valid(_content):
		_content.shutdown()
	if is_instance_valid(_dock):
		remove_dock(_dock)
		_dock.queue_free()
	_content = null
	_dock = null
