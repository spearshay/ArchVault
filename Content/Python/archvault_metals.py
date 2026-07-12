"""
ArchVault metal instance builder — manifest-driven MIC hierarchy for metals.

Reads metal_manifest.json (same folder) and creates/updates:
  MI_Metal_Base -> MI_<Metal> -> MI_<Metal>_<Finish>
under the instance folder, parented to M_Metal_Master.

Idempotent: re-running updates parameters in place, so tweak the manifest
(tints, roughness bands, aging) and re-run instead of editing instances by
hand. See docs/METAL_SYSTEM.md for the master build spec and workflow.

Usage (UE Python console, editor open):
    import archvault_metals
    archvault_metals.build()             # create/update everything
    archvault_metals.build(dry_run=True) # log what would change, touch nothing
    archvault_metals.import_finish_textures(r"D:/authored/maps")
"""
import os
import json
import unreal

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_MANIFEST = os.path.join(_THIS_DIR, "metal_manifest.json")

# Parameter names on M_Metal_Master — keep in sync with docs/METAL_SYSTEM.md.
P_TINT = "Metal Tint"
P_METALLIC = "Metallic"
P_ROUGHNESS = "Roughness"          # scalar, used when Use Roughness Map is OFF
P_ROUGH_TEX = "Finish Roughness"   # single-channel grayscale, used when ON
P_ROUGH_MIN = "Roughness Min"
P_ROUGH_MAX = "Roughness Max"
P_NORMAL = "Finish Normal"
P_NORMAL_STR = "Normal Strength"
P_ANISO_STR = "Anisotropy Strength"
P_AGING_MASK = "Aging Mask"
P_AGING_AMT = "Aging Amount"
P_AGED_TINT = "Aged Tint"
P_AGED_ROUGH = "Aged Roughness"
P_AGED_METAL_DROP = "Aged Metallic Drop"
S_USE_ROUGH_MAP = "Use Roughness Map"
S_USE_NORMAL = "Use Finish Normal"
S_USE_ANISO = "Use Anisotropy"
S_USE_AGING = "Use Aging"

_MEL = unreal.MaterialEditingLibrary
_EAL = unreal.EditorAssetLibrary


def _load_manifest():
    with open(_MANIFEST, "r") as f:
        return json.load(f)


def _color(rgb):
    return unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0)


def _get_or_create_mic(folder, name, dry_run):
    path = "%s/%s" % (folder, name)
    if _EAL.does_asset_exist(path):
        return _EAL.load_asset(path), False
    if dry_run:
        unreal.log("[dry-run] would create %s" % path)
        return None, True
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mic = tools.create_asset(name, folder, unreal.MaterialInstanceConstant,
                             unreal.MaterialInstanceConstantFactoryNew())
    if mic is None:
        raise RuntimeError("Failed to create %s" % path)
    return mic, True


def _set_static_switch(mic, name, value):
    # Available in UE 5.1+; harmless no-op with a warning on older builds.
    fn = getattr(_MEL, "set_material_instance_static_switch_parameter_value", None)
    if fn is None:
        unreal.log_warning("MaterialEditingLibrary lacks static-switch setter; "
                           "set '%s'=%s on %s manually" % (name, value, mic.get_name()))
        return
    fn(mic, name, value)


def _texture(finishes_folder, tex_name):
    if not tex_name:
        return None
    path = "%s/%s" % (finishes_folder, tex_name)
    if not _EAL.does_asset_exist(path):
        unreal.log_warning("Finish texture missing: %s (skipping assignment)" % path)
        return None
    return _EAL.load_asset(path)


def _apply_finish(mic, finish, metal, m, finishes_folder):
    """Write one finish recipe onto an instance."""
    # Roughness: scalar path (no map) vs. grayscale-map path (remapped by min/max).
    rough_map = _texture(finishes_folder, finish.get("rough_map"))
    _set_static_switch(mic, S_USE_ROUGH_MAP, rough_map is not None)
    if rough_map is not None:
        _MEL.set_material_instance_texture_parameter_value(mic, P_ROUGH_TEX, rough_map)
        _MEL.set_material_instance_scalar_parameter_value(mic, P_ROUGH_MIN, finish.get("rough_min", 0.05))
        _MEL.set_material_instance_scalar_parameter_value(mic, P_ROUGH_MAX, finish.get("rough_max", 0.15))
    else:
        _MEL.set_material_instance_scalar_parameter_value(mic, P_ROUGHNESS, finish.get("roughness", 0.08))

    normal = _texture(finishes_folder, finish.get("normal"))
    _set_static_switch(mic, S_USE_NORMAL, normal is not None)
    if normal:
        _MEL.set_material_instance_texture_parameter_value(mic, P_NORMAL, normal)
        _MEL.set_material_instance_scalar_parameter_value(
            mic, P_NORMAL_STR, finish.get("normal_strength", 1.0))

    aniso = finish.get("anisotropy")
    _set_static_switch(mic, S_USE_ANISO, aniso is not None)
    if aniso is not None:
        _MEL.set_material_instance_scalar_parameter_value(mic, P_ANISO_STR, aniso)

    aging = finish.get("aging")
    _set_static_switch(mic, S_USE_AGING, aging is not None)
    if aging is not None:
        _MEL.set_material_instance_scalar_parameter_value(mic, P_AGING_AMT, aging)
        _MEL.set_material_instance_scalar_parameter_value(
            mic, P_AGED_ROUGH, finish.get("aged_roughness", 0.65))
        _MEL.set_material_instance_scalar_parameter_value(
            mic, P_AGED_METAL_DROP, finish.get("aged_metallic_drop", 0.15))
        aged_tint = finish.get("aged_tint_override") or m.get("aged_tint")
        if aged_tint:
            _MEL.set_material_instance_vector_parameter_value(mic, P_AGED_TINT, _color(aged_tint))


def build(dry_run=False):
    """Create/update the whole metal MIC hierarchy from the manifest."""
    cfg = _load_manifest()
    folder = cfg["instance_folder"]
    finishes_folder = cfg["finishes_folder"]

    master = _EAL.load_asset(cfg["master"]) if _EAL.does_asset_exist(cfg["master"]) else None
    if master is None:
        unreal.log_error("Master not found: %s — build it first "
                         "(see docs/METAL_SYSTEM.md §3)" % cfg["master"])
        return

    touched = []

    # 1) Base instance: parent for every metal, neutral defaults.
    base, _ = _get_or_create_mic(folder, cfg["base_instance"], dry_run)
    if base is not None:
        _MEL.set_material_instance_parent(base, master)
        _MEL.set_material_instance_vector_parameter_value(
            base, P_TINT, _color(cfg["metals"]["Steel"]["tint"]))
        _MEL.set_material_instance_scalar_parameter_value(base, P_METALLIC, 1.0)
        touched.append(base)

    # 2) Per-metal parents (always created) + per-finish children (from 'build').
    for metal, m in cfg["metals"].items():
        parent_mic, _ = _get_or_create_mic(folder, "MI_%s" % metal, dry_run)
        if parent_mic is not None:
            if base is not None:
                _MEL.set_material_instance_parent(parent_mic, base)
            _MEL.set_material_instance_vector_parameter_value(parent_mic, P_TINT, _color(m["tint"]))
            if m.get("aged_tint"):
                _MEL.set_material_instance_vector_parameter_value(
                    parent_mic, P_AGED_TINT, _color(m["aged_tint"]))
            _apply_finish(parent_mic, cfg["finishes"]["Polished"], metal, m, finishes_folder)
            touched.append(parent_mic)

        for finish_name in cfg["build"].get(metal, []):
            finish = cfg["finishes"].get(finish_name)
            if finish is None:
                unreal.log_warning("Unknown finish '%s' for %s — skipped" % (finish_name, metal))
                continue
            child, _ = _get_or_create_mic(folder, "MI_%s_%s" % (metal, finish_name), dry_run)
            if child is None:
                continue
            if parent_mic is not None:
                _MEL.set_material_instance_parent(child, parent_mic)
            _apply_finish(child, finish, metal, m, finishes_folder)
            touched.append(child)

    if dry_run:
        unreal.log("[dry-run] done — %d instances would be written" % len(touched))
        return

    for mic in touched:
        _MEL.update_material_instance(mic)
        _EAL.save_loaded_asset(mic)
    unreal.log("ArchVault metals: %d instances created/updated in %s" % (len(touched), folder))


def import_finish_textures(source_dir):
    """Import authored finish maps with correct settings.

    *_N.* -> Normalmap compression;  everything else (roughness/masks) ->
    single-channel Grayscale. sRGB off for all. Metals don't pack, so finish
    roughness maps are grayscale, not RGB masks.
    """
    cfg = _load_manifest()
    dest = cfg["finishes_folder"]
    files = [f for f in os.listdir(source_dir)
             if f.lower().endswith((".png", ".tga", ".tif", ".tiff", ".exr"))]
    if not files:
        unreal.log_warning("No image files found in %s" % source_dir)
        return

    tasks = []
    for f in files:
        t = unreal.AssetImportTask()
        t.filename = os.path.join(source_dir, f)
        t.destination_path = dest
        t.automated = True
        t.replace_existing = True
        t.save = False
        tasks.append(t)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

    for f in files:
        name = os.path.splitext(f)[0]
        path = "%s/%s" % (dest, name)
        tex = _EAL.load_asset(path) if _EAL.does_asset_exist(path) else None
        if tex is None:
            unreal.log_warning("Import produced no asset for %s" % f)
            continue
        is_normal = name.lower().endswith("_n")
        tex.set_editor_property("srgb", False)
        tex.set_editor_property(
            "compression_settings",
            unreal.TextureCompressionSettings.TC_NORMALMAP if is_normal
            else unreal.TextureCompressionSettings.TC_GRAYSCALE)
        _EAL.save_loaded_asset(tex)
        unreal.log("Imported %s (%s, sRGB off)" % (path, "Normalmap" if is_normal else "Grayscale"))
