"""
ArchVault M_Metal_Master builder — constructs the whole material graph in code.

Run inside UE (Python console) so you don't have to hand-wire the node graph
from docs/METAL_SYSTEM.md:

    import archvault_build_master
    archvault_build_master.build()          # clean rebuild
    archvault_build_master.build(force=True) # rebuild even if referenced

Design = docs/METAL_SYSTEM.md Revision 2 (single-channel roughness + scalar
metallic/AO). Parameter names here MUST match archvault_metals.py exactly, or
the instance builder won't find them.

CLEAN REBUILD: deletes an existing /ArchVault/Masters/M_Metal_Master if it has
no referencers (abort with a message if it does, unless force=True), then
builds fresh. Idempotent — safe to re-run.

Built to be run against a *live* editor and iterated on: each subsystem is
wrapped so one UE-API mismatch logs a clear error instead of aborting the whole
build. If a connection warns about a pin name (e.g. static-switch "True"/"False"),
fix that one constant and re-run.
"""
import unreal

MASTER_PATH = "/ArchVault/Masters/M_Metal_Master"
MASTER_NAME = "M_Metal_Master"
MASTER_DIR = "/ArchVault/Masters"
MF_UV_CONTROL = "/ArchVault/Functions/MF_UVControl"  # same UV control as M_Opaque_Master

# Parameter names — keep identical to archvault_metals.py.
P_TINT = "Metal Tint"
P_METALLIC = "Metallic"
P_AO = "AO"
P_ROUGHNESS = "Roughness"
P_ROUGH_TEX = "Finish Roughness"
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

G_BASE, G_FINISH, G_AGING = "Base", "Finish", "Aging"

# Static-switch input pin names (fix here if the live editor reports otherwise).
SW_TRUE, SW_FALSE = "True", "False"

_MEL = unreal.MaterialEditingLibrary
_EAL = unreal.EditorAssetLibrary

# Engine fallback textures so texture-sample params compile before instances
# override them. First existing wins.
_GRAY_CANDIDATES = [
    "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture",
    "/Engine/EngineResources/DefaultTexture.DefaultTexture",
]
_NORMAL_CANDIDATES = [
    "/Engine/EngineMaterials/DefaultNormal.DefaultNormal",
    "/Engine/EngineResources/DefaultTexture.DefaultTexture",
]


def _first_existing(paths):
    for p in paths:
        if _EAL.does_asset_exist(p.split(".")[0]):
            return _EAL.load_asset(p.split(".")[0])
    return None


# ---- graph helpers ---------------------------------------------------------

def _node(mat, cls, x, y):
    return _MEL.create_material_expression(mat, cls, x, y)


def _wire(a, a_out, b, b_in):
    """Connect expression a[a_out] -> b[b_in], logging on failure."""
    try:
        ok = _MEL.connect_material_expressions(a, a_out, b, b_in)
        if not ok:
            unreal.log_warning("wire failed: [%s] -> [%s] (out=%r in=%r)"
                               % (a.get_name(), b.get_name(), a_out, b_in))
        return ok
    except Exception as e:
        unreal.log_warning("wire error %s -> %s: %s" % (a.get_name(), b.get_name(), e))
        return False


def _to_prop(a, a_out, prop):
    try:
        _MEL.connect_material_property(a, a_out, prop)
    except Exception as e:
        unreal.log_warning("property connect error (%s): %s" % (prop, e))


def _scalar(mat, name, default, group, x, y):
    n = _node(mat, unreal.MaterialExpressionScalarParameter, x, y)
    n.set_editor_property("parameter_name", name)
    n.set_editor_property("default_value", float(default))
    n.set_editor_property("group", group)
    return n


def _vector(mat, name, rgb, group, x, y):
    n = _node(mat, unreal.MaterialExpressionVectorParameter, x, y)
    n.set_editor_property("parameter_name", name)
    n.set_editor_property("default_value", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    n.set_editor_property("group", group)
    return n


def _switch(mat, name, default, group, x, y):
    n = _node(mat, unreal.MaterialExpressionStaticSwitchParameter, x, y)
    n.set_editor_property("parameter_name", name)
    n.set_editor_property("default_value", bool(default))
    n.set_editor_property("group", group)
    return n


def _texparam(mat, name, group, sampler_type, default_tex, x, y):
    n = _node(mat, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    n.set_editor_property("parameter_name", name)
    n.set_editor_property("group", group)
    if default_tex is not None:
        n.set_editor_property("texture", default_tex)
    try:
        n.set_editor_property("sampler_type", sampler_type)
    except Exception as e:
        unreal.log_warning("sampler_type set failed on %s: %s" % (name, e))
    return n


def _const(mat, value, x, y):
    n = _node(mat, unreal.MaterialExpressionConstant, x, y)
    n.set_editor_property("r", float(value))
    return n


def _const3(mat, rgb, x, y):
    n = _node(mat, unreal.MaterialExpressionConstant3Vector, x, y)
    n.set_editor_property("constant", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    return n


def _lerp(mat, x, y):
    return _node(mat, unreal.MaterialExpressionLinearInterpolate, x, y)


def _mul(mat, x, y):
    return _node(mat, unreal.MaterialExpressionMultiply, x, y)


def _sub(mat, x, y):
    return _node(mat, unreal.MaterialExpressionSubtract, x, y)


# ---- build -----------------------------------------------------------------

def _delete_existing(force):
    if not _EAL.does_asset_exist(MASTER_PATH):
        return True
    refs = _EAL.find_package_referencers_for_asset(MASTER_PATH)
    if refs and not force:
        unreal.log_error(
            "M_Metal_Master has %d referencer(s); aborting clean rebuild. "
            "Re-point/retire them first, or call build(force=True). Referencers: %s"
            % (len(refs), refs))
        return False
    if not _EAL.delete_asset(MASTER_PATH):
        unreal.log_error("Could not delete existing M_Metal_Master.")
        return False
    unreal.log("Deleted existing M_Metal_Master for clean rebuild.")
    return True


def build(force=False):
    if not _delete_existing(force):
        return None

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(MASTER_NAME, MASTER_DIR, unreal.Material,
                             unreal.MaterialFactoryNew())
    if mat is None:
        unreal.log_error("Failed to create M_Metal_Master.")
        return None
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)

    gray = _first_existing(_GRAY_CANDIDATES)
    flat_normal_tex = _first_existing(_NORMAL_CANDIDATES)
    ST_GRAY = unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE
    ST_NORMAL = unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL

    # ---- parameters ----
    tint = _vector(mat, P_TINT, [0.910, 0.778, 0.423], G_BASE, -1600, -400)
    metallic = _scalar(mat, P_METALLIC, 1.0, G_BASE, -1600, -250)
    ao = _scalar(mat, P_AO, 1.0, G_BASE, -1600, -150)

    use_rmap = _switch(mat, S_USE_ROUGH_MAP, False, G_FINISH, -800, 100)
    rough_scalar = _scalar(mat, P_ROUGHNESS, 0.08, G_FINISH, -1600, 50)
    rough_tex = _texparam(mat, P_ROUGH_TEX, G_FINISH, ST_GRAY, gray, -1600, 150)
    rmin = _scalar(mat, P_ROUGH_MIN, 0.05, G_FINISH, -1600, 320)
    rmax = _scalar(mat, P_ROUGH_MAX, 0.15, G_FINISH, -1600, 400)

    use_normal = _switch(mat, S_USE_NORMAL, False, G_FINISH, -400, 700)
    normal_tex = _texparam(mat, P_NORMAL, G_FINISH, ST_NORMAL, flat_normal_tex, -1600, 650)
    normal_str = _scalar(mat, P_NORMAL_STR, 1.0, G_FINISH, -1600, 850)

    use_aniso = _switch(mat, S_USE_ANISO, False, G_FINISH, -400, 1000)
    aniso_str = _scalar(mat, P_ANISO_STR, 0.6, G_FINISH, -1600, 1000)

    use_aging = _switch(mat, S_USE_AGING, False, G_AGING, -200, -200)
    aging_mask = _texparam(mat, P_AGING_MASK, G_AGING, ST_GRAY, gray, -1600, 1200)
    aging_amt = _scalar(mat, P_AGING_AMT, 0.5, G_AGING, -1600, 1380)
    aged_tint = _vector(mat, P_AGED_TINT, [0.18, 0.12, 0.07], G_AGING, -1600, 1480)
    aged_rough = _scalar(mat, P_AGED_ROUGH, 0.65, G_AGING, -1600, 1600)
    aged_metal_drop = _scalar(mat, P_AGED_METAL_DROP, 0.15, G_AGING, -1600, 1700)

    # ---- shared aging factor: mask.R * amount ----
    aging_factor = _mul(mat, -1200, 1300)
    _wire(aging_mask, "R", aging_factor, "A")
    _wire(aging_amt, "", aging_factor, "B")

    # ---- base color: switch(aging, tint, lerp(tint, aged, factor)) ----
    aged_color = _lerp(mat, -600, -350)
    _wire(tint, "", aged_color, "A")
    _wire(aged_tint, "", aged_color, "B")
    _wire(aging_factor, "", aged_color, "Alpha")
    bc_switch = _switch(mat, S_USE_AGING + " (BaseColor)", False, G_AGING, -200, -400)
    bc_switch.set_editor_property("parameter_name", S_USE_AGING)  # share the same param
    _wire(tint, "", bc_switch, SW_FALSE)
    _wire(aged_color, "", bc_switch, SW_TRUE)
    _to_prop(bc_switch, "", unreal.MaterialProperty.MP_BASE_COLOR)

    # ---- roughness: base = switch(rmap, scalar, lerp(min,max,tex.R)) ----
    rough_remap = _lerp(mat, -1000, 200)
    _wire(rmin, "", rough_remap, "A")
    _wire(rmax, "", rough_remap, "B")
    _wire(rough_tex, "R", rough_remap, "Alpha")
    _wire(rough_scalar, "", use_rmap, SW_FALSE)
    _wire(rough_remap, "", use_rmap, SW_TRUE)
    # then aging: switch(aging, base, lerp(base, agedRough, factor))
    rough_aged = _lerp(mat, -400, 250)
    _wire(use_rmap, "", rough_aged, "A")
    _wire(aged_rough, "", rough_aged, "B")
    _wire(aging_factor, "", rough_aged, "Alpha")
    rough_switch = _switch(mat, S_USE_AGING + " (Roughness)", False, G_AGING, -100, 200)
    rough_switch.set_editor_property("parameter_name", S_USE_AGING)
    _wire(use_rmap, "", rough_switch, SW_FALSE)
    _wire(rough_aged, "", rough_switch, SW_TRUE)
    _to_prop(rough_switch, "", unreal.MaterialProperty.MP_ROUGHNESS)

    # ---- metallic: switch(aging, metallic, clamp(metallic - factor*drop)) ----
    drop_mul = _mul(mat, -800, 500)
    _wire(aging_factor, "", drop_mul, "A")
    _wire(aged_metal_drop, "", drop_mul, "B")
    metal_sub = _sub(mat, -600, 480)
    _wire(metallic, "", metal_sub, "A")
    _wire(drop_mul, "", metal_sub, "B")
    metal_clamp = _node(mat, unreal.MaterialExpressionClamp, -450, 480)
    metal_clamp.set_editor_property("min_default", 0.0)
    metal_clamp.set_editor_property("max_default", 1.0)
    _wire(metal_sub, "", metal_clamp, "")
    metal_switch = _switch(mat, S_USE_AGING + " (Metallic)", False, G_AGING, -200, 450)
    metal_switch.set_editor_property("parameter_name", S_USE_AGING)
    _wire(metallic, "", metal_switch, SW_FALSE)
    _wire(metal_clamp, "", metal_switch, SW_TRUE)
    _to_prop(metal_switch, "", unreal.MaterialProperty.MP_METALLIC)

    # ---- AO ----
    _to_prop(ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

    # ---- normal: switch(useNormal, flat, lerp(flat, tex.RGB, strength)) ----
    flat = _const3(mat, [0.0, 0.0, 1.0], -800, 800)
    flattened = _lerp(mat, -600, 720)
    _wire(flat, "", flattened, "A")
    _wire(normal_tex, "RGB", flattened, "B")
    _wire(normal_str, "", flattened, "Alpha")
    _wire(flat, "", use_normal, SW_FALSE)
    _wire(flattened, "", use_normal, SW_TRUE)
    _to_prop(use_normal, "", unreal.MaterialProperty.MP_NORMAL)

    # ---- anisotropy: switch(useAniso, 0, strength) ----
    zero = _const(mat, 0.0, -800, 1050)
    _wire(zero, "", use_aniso, SW_FALSE)
    _wire(aniso_str, "", use_aniso, SW_TRUE)
    try:
        _to_prop(use_aniso, "", unreal.MaterialProperty.MP_ANISOTROPY)
    except Exception as e:
        unreal.log_warning("Anisotropy pin not available (%s) — skip; wire manually." % e)

    # ---- UVs via MF_UVControl (Tiling / Offset / Rotation + per-instance random) ----
    # Same UV control as M_Opaque_Master. The call node feeds every sampler's UVs input;
    # its params (UV Scale U/V, UV Offset U/V, UV Rotation, ...) are promoted onto the
    # master and become overridable per instance — that's the "UV controls" surface.
    if _EAL.does_asset_exist(MF_UV_CONTROL):
        uv = _node(mat, unreal.MaterialExpressionMaterialFunctionCall, -2200, 300)
        uv.set_editor_property("material_function", _EAL.load_asset(MF_UV_CONTROL))
        for samp in (rough_tex, normal_tex, aging_mask):
            # MF output pin name varies by function; keep the first candidate that connects.
            # connect_material_expressions returns False (doesn't raise) on a wrong output name.
            if not any(_MEL.connect_material_expressions(uv, out, samp, "UVs")
                       for out in ("", "Result", "UV", "UVs", "Output")):
                unreal.log_warning("MF_UVControl -> %s UVs failed (no matching output pin)"
                                   % samp.get_name())
    else:
        unreal.log_warning("MF_UVControl not found — samplers use default UVs.")

    # ---- finalize ----
    try:
        _MEL.layout_material_expressions(mat)
    except Exception:
        pass
    _MEL.recompile_material(mat)
    _EAL.save_loaded_asset(mat)
    unreal.log("M_Metal_Master built. Next: archvault_metals.build(dry_run=True) to verify "
               "param names, then archvault_metals.build().")
    return mat
