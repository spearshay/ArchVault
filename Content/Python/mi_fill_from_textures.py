"""mi_fill_from_textures.py - "map-drop": fill a material instance from its texture set.

Usage (ArchVault menu > Fill MI from Textures), either:
- one click: select ONE material instance plus its textures (or a texture FOLDER), click; or
- two clicks (MI and textures in different folders): select ONLY the MI, click (it's remembered),
  then select its textures or their folder, click again.

What it does:
- Sorts the textures into slots by filename suffix (SUFFIXES below).
- Data maps -> sRGB off; Compression Default (normals -> Normalmap). Albedo -> sRGB on.
- Reads the MI's texture params + static switches LIVE from its parent and fills only the ones
  that exist (PARAMS below), ticking the matching "Use ..." switches. The setters create the
  override entry, so exactly the params it sets get their override box ticked - nothing else.
- OpenGL normals (name says GL / OGL / OpenGL right after the normal token, e.g. Brick_Normal_GL_2K,
  nrm-ogl, NormalOpenGL) -> ticks Flip Green Channel on the texture (only ever ticks it, never unticks).
  A normal whose name says NEITHER GL nor DX is LEFT ALONE and flagged (Shay, 2026-11-23: vendors vary,
  the old "assume OpenGL" guess was wrong too often - only flip on evidence).
  DX-named normals are left alone. Given _Normal + _NormalDX, the DX one is used.
- ORM / ARM packs (R=AO G=Rough B=Metal, Poliigon/glTF) -> "ORM Map" + Use Packed ORM, which on its
  own drives all three channels (master is ORM since 2026-11-17).
- Flags instead of guessing: GLOSS (needs inverting), RMA packs (channel order is not the
  master's ORM), REFL (spec/gloss reflectance, not UE Specular), Height/Displacement (no slot),
  a DirectX-named normal that is already flipped, two textures for one slot.
- Saves the MI + any texture whose settings changed; refreshes an open MI editor.

Check MI Texture Settings (second menu entry, check_run): select MIs or a folder of them; every texture
an MI overrides is matched to the master's sampler for that slot (Color = sRGB on, Linear = sRGB off,
Normal = Normalmap, Grayscale/Masks likewise) and fixed + saved. Catches maps dropped on by hand.

Canonical copy: E:\\My Drive\\AI\\Claude\\UE\\mi_swap\\mi_fill_from_textures.py
Deployed copy:  <UE_5.8>\\Engine\\Plugins\\ArchVault\\Content\\Python\\ (menu in init_unreal.py)
"""
import re
import unreal

mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary

# suffix (lowercase, separators removed) -> slot. Built from the COLTVET texture sets 2026-11-10.
SUFFIXES = {
    "albedo": ["basecolor", "albedo", "diffuse", "diff", "col", "color"],
    "normal": ["normal", "nrm", "nrm16", "nor", "normaldx", "normalgl", "nrmgl"],
    "roughness": ["roughness", "rough", "specularroughness"],
    "metallic": ["metallic", "metalness", "basemetalness"],
    "ao": ["ambientocclusion", "ao", "occlusion"],
    "specular": ["specular", "spec"],
    "orm": ["orm", "arm"],
}
# matched but deliberately NOT assigned -> reported
FLAGS = {
    "gloss": "GLOSS = glossiness (inverse of roughness) - needs inverting first, not assigned",
    "glossiness": "GLOSS = glossiness (inverse of roughness) - needs inverting first, not assigned",
    "rma": "RMA pack (R=Rough G=Metal B=AO) - master ORM Map is R=AO G=Rough B=Metal; repack, not assigned",
    "refl": "REFL = spec/gloss reflectance (F0), not UE Specular (0.5 = 4%) - not assigned",
    "reflection": "REFL = spec/gloss reflectance (F0), not UE Specular (0.5 = 4%) - not assigned",
    "height": "Height - no slot on the master, skipped",
    "displacement": "Displacement - no slot on the master, skipped",
    "disp": "Displacement - no slot on the master, skipped",
    "disp16": "Displacement - no slot on the master, skipped",
    "bump": "Bump - no slot on the master, skipped",
}
# slot -> (texture param candidates, switches to tick). Only names that exist on the parent are used.
PARAMS = {
    "albedo": (["Albedo"], ["Use Albedo Map"]),
    "normal": (["Normal", "Finish Normal"], ["Use Normal Map"]),
    "roughness": (["Roughness", "Finish Roughness"], ["Use Roughness Map"]),
    "metallic": (["Metallic"], ["Use Metallic Mask"]),
    "ao": (["Ambient Occlusion"], ["Use AO Mask"]),
    "specular": (["Specular"], ["Use Specular Map"]),
    # Use Packed ORM alone drives AO/roughness/metal (output-side switches in M_Opaque_Master since 2026-11-17)
    "orm": (["ORM Map"], ["Use Packed ORM"]),
}
_LOOKUP = {s: slot for slot, sfx in SUFFIXES.items() for s in sfx}
_RES = re.compile(r"^(\d+k|\d+)$")  # resolution / index tokens: 2K, 4K, 001
# normal-map convention markers; only honoured right after the normal token (or fused onto it)
GL_MARKS = ("opengl", "ogl", "gl")
DX_MARKS = ("directx", "dx")


def classify(name):
    """Return (slot | None, flag_message | None, convention) for a texture asset name.
    convention = "gl" / "dx" for a normal map whose name says so, else None."""
    toks = [t.lower() for t in re.split(r"[_\-\s.]+", name) if t]
    conv = None
    # Poliigon legacy names end in the WORKFLOW, not the map: Name_NRM_4K_METALNESS / _COL_4K_SPECULAR
    if len(toks) >= 3 and toks[-1] in ("metalness", "specular") and _RES.match(toks[-2]):
        toks.pop()
    while toks:  # strip trailing resolution/index tokens and ONE convention marker, in any order
        if _RES.match(toks[-1]):
            toks.pop()
        elif conv is None and toks[-1] in GL_MARKS + DX_MARKS:
            conv = "gl" if toks.pop() in GL_MARKS else "dx"
        else:
            break
    cands = ["".join(toks[-2:])] if len(toks) >= 2 else []
    cands += toks[-1:]
    for c in cands:
        if c in FLAGS:
            return None, FLAGS[c], None
        if c in _LOOKUP:
            slot = _LOOKUP[c]
            if slot != "normal":
                return slot, None, None
            if conv is None:  # fused marker already in SUFFIXES: NormalGL, NrmGL, NormalDX
                conv = "gl" if c.endswith(GL_MARKS) else "dx" if c.endswith(DX_MARKS) else None
            return slot, None, conv
        for b in SUFFIXES["normal"]:  # fused marker on a plain normal token not in the list
            for m in GL_MARKS + DX_MARKS:
                if c == b + m:
                    return "normal", None, "gl" if m in GL_MARKS else "dx"
    return None, None, None


def _pkg(o):
    return o.get_path_name().split(".")[0]


def _fix_texture(tex, slot, res, conv=None):
    """sRGB/compression by slot (+ Flip Green for OpenGL-named normals). Returns True if changed.
    Compression goes FIRST: UE forces sRGB off while compression is Masks/Normalmap/etc., so an
    sRGB set before the compression change gets undone (seen in 5.8 test, 2026-11-10)."""
    tc = unreal.TextureCompressionSettings
    want_srgb = slot == "albedo"
    cur_tc = tex.get_editor_property("compression_settings")
    if slot == "normal":
        want_tc = tc.TC_NORMALMAP
    elif slot == "albedo":
        want_tc = cur_tc if cur_tc in (tc.TC_DEFAULT, tc.TC_BC7) else tc.TC_DEFAULT
    elif slot == "orm":
        want_tc = tc.TC_BC7  # 3 unrelated channels: BC1 (Default) crushes the subtle one, usually roughness
    else:
        want_tc = tc.TC_DEFAULT
    changes = []
    if cur_tc != want_tc:
        tex.set_editor_property("compression_settings", want_tc)
        changes.append("Compression %s" % want_tc.name)
    if tex.get_editor_property("srgb") != want_srgb:
        tex.set_editor_property("srgb", want_srgb)
        changes.append("sRGB %s" % ("on" if want_srgb else "off"))
    if tex.get_editor_property("srgb") != want_srgb:
        res["errors"].append("%s: sRGB would not change to %s" % (tex.get_name(), want_srgb))
    if slot == "normal":
        flipped = tex.get_editor_property("flip_green_channel")
        if conv == "gl" and not flipped:
            tex.set_editor_property("flip_green_channel", True)
            changes.append("Flip Green Channel on (OpenGL name)")
        elif conv is None:
            res["flags"].append("%s: name says neither GL nor DX - Flip Green Channel left %s; "
                                "if bumps read as dents, toggle it" % (tex.get_name(), "on" if flipped else "off"))
        elif conv == "dx" and flipped:
            res["flags"].append("%s: name says DirectX but Flip Green Channel is ticked - check it" % tex.get_name())
    if changes:
        res["textures_changed"].append("%s: %s" % (tex.get_name(), ", ".join(changes)))
    return bool(changes)


def fill(mi, textures, save=True):
    """Fill material instance `mi` from `textures`. Returns a result dict (also the report)."""
    res = {"mi": _pkg(mi), "parent": None, "set": [], "switches": [], "textures_changed": [],
           "flags": [], "unmatched": [], "errors": []}
    parent = mi.get_editor_property("parent")
    if not parent:
        res["errors"].append("MI has no parent material")
        return res
    res["parent"] = _pkg(parent)
    tex_params = {str(n) for n in mel.get_texture_parameter_names(parent)}
    switch_params = {str(n) for n in mel.get_static_switch_parameter_names(parent)}

    # 1. sort into slots
    slots = {}
    for t in textures:
        if _pkg(mi).startswith("/Game/") and _pkg(t).startswith("/ArchVault/"):
            res["errors"].append("%s is in /ArchVault - a /Game MI must not reference the library; "
                                 "copy it into the project first. Skipped." % t.get_name())
            continue
        slot, flag, conv = classify(t.get_name())
        if flag:
            res["flags"].append("%s: %s" % (t.get_name(), flag))
        elif slot:
            slots.setdefault(slot, []).append((t, conv))
        else:
            res["unmatched"].append(t.get_name())

    # 2. one texture per slot (given several normals, prefer the one DX-named), else flag
    for slot, lst in sorted(slots.items()):
        if len(lst) > 1:
            dx = [x for x in lst if x[1] == "dx"]
            if slot == "normal" and len(dx) == 1:
                lst = dx
            else:
                res["flags"].append("%s: %d textures (%s) - pick one by hand, not assigned" % (
                    slot, len(lst), ", ".join(x[0].get_name() for x in lst)))
                continue
        tex, conv = lst[0]
        names, switches = PARAMS[slot]
        param = next((n for n in names if n in tex_params), None)
        if not param:
            res["flags"].append("%s: %s - parent has no %s param (looked for %s), not assigned" % (
                slot, tex.get_name(), slot, "/".join(names)))
            continue
        changed = _fix_texture(tex, slot, res, conv)
        if changed and save:
            eal.save_loaded_asset(tex, False)
        mel.set_material_instance_texture_parameter_value(mi, param, tex)
        res["set"].append("%s <- %s" % (param, tex.get_name()))
        for sw in switches:
            if sw in switch_params and sw not in res["switches"]:
                mel.set_material_instance_static_switch_parameter_value(mi, sw, True)
                res["switches"].append(sw)

    if res["set"]:
        mel.update_material_instance(mi)
        mel.refresh_material_instance_editor(mi)
        if save:
            eal.save_loaded_asset(mi, False)
    return res


def _selected_folders():
    """Selected Content Browser folders as real asset paths. The browser reports VIRTUAL paths
    (/All/Game/X, /All/EngineData/Plugins/ArchVault/X, /All/Plugins/...), so take the shortest tail that
    is an existing asset directory: /Game/X, /ArchVault/X."""
    eul = unreal.EditorUtilityLibrary
    virtual = list(eul.get_selected_folder_paths())
    if hasattr(eul, "get_selected_path_view_folder_paths"):  # folders picked in the left-hand tree
        virtual += [p for p in eul.get_selected_path_view_folder_paths() if p not in virtual]
    out = []
    for v in virtual:
        segs = [s for s in str(v).split("/") if s]
        real = next(("/" + "/".join(segs[i:]) for i in range(len(segs))
                     if eal.does_directory_exist("/" + "/".join(segs[i:]))), None)
        if real and real not in out:
            out.append(real)
    unreal.log("ArchVault selection: folders %s -> %s" % (virtual, out))
    return out


def _textures_from_selection(assets):
    texs = [a for a in assets if isinstance(a, unreal.Texture2D)]
    if texs:
        return texs
    for folder in _selected_folders():
        for p in eal.list_assets(folder, recursive=True, include_folder=False):
            a = unreal.load_asset(p.split(".")[0])
            if isinstance(a, unreal.Texture2D):
                texs.append(a)
    return texs


def report_text(res):
    lines = ["%s  (parent %s)" % (res["mi"], res["parent"])]
    for key, title in [("set", "Filled (override ticked)"), ("switches", "Switches ON (override ticked)"),
                       ("textures_changed", "Texture settings fixed"), ("flags", "FLAGGED - check these"),
                       ("unmatched", "No suffix match (ignored)"), ("errors", "Errors")]:
        if res[key]:
            lines.append("\n%s:" % title)
            lines += ["  " + x for x in res[key]]
    if not res["set"]:
        lines.append("\nNothing was filled.")
    return "\n".join(lines)


# ---- Check MI Texture Settings: fix any texture an MI uses whose sRGB/compression doesn't match the
# master's sampler for that slot (catches maps dropped on by hand, which skip _fix_texture). ----
_TC = unreal.TextureCompressionSettings
# sampler type name -> (compressions accepted as-is, compression to set otherwise, sRGB)
_SAMPLER_WANTS = {
    "SAMPLERTYPE_COLOR": ((_TC.TC_DEFAULT, _TC.TC_BC7), _TC.TC_DEFAULT, True),
    "SAMPLERTYPE_LINEAR_COLOR": ((_TC.TC_DEFAULT, _TC.TC_BC7), _TC.TC_DEFAULT, False),
    "SAMPLERTYPE_NORMAL": ((_TC.TC_NORMALMAP,), _TC.TC_NORMALMAP, False),
    "SAMPLERTYPE_GRAYSCALE": ((_TC.TC_GRAYSCALE,), _TC.TC_GRAYSCALE, True),
    "SAMPLERTYPE_LINEAR_GRAYSCALE": ((_TC.TC_GRAYSCALE,), _TC.TC_GRAYSCALE, False),
    "SAMPLERTYPE_MASKS": ((_TC.TC_MASKS,), _TC.TC_MASKS, False),
}
# per-parameter overrides of the above (packed maps: BC7 keeps all three channels' detail)
_PARAM_WANTS = {"ORM Map": ((_TC.TC_BC7,), _TC.TC_BC7, False)}


def _samplers(material):
    """param name -> sampler type name, for every texture parameter node in the base material."""
    out = {}
    for e in unreal.ObjectIterator(unreal.MaterialExpressionTextureSampleParameter):
        if e.get_outer() == material:
            out[str(e.get_editor_property("parameter_name"))] = e.get_editor_property("sampler_type").name
    return out


def check_textures(mis, fix=True):
    """For each MI's own texture overrides: make the texture match its slot's sampler. Returns a report dict."""
    res = {"checked": 0, "textures_changed": [], "ok": 0, "flags": [], "errors": []}
    cache, done = {}, set()
    for mi in mis:
        base = mi.get_base_material()
        if not base:
            res["errors"].append("%s: no base material" % mi.get_name())
            continue
        samp = cache.setdefault(_pkg(base), _samplers(base))
        res["checked"] += 1
        for tp in mi.get_editor_property("texture_parameter_values"):
            name, tex = str(tp.parameter_info.name), tp.parameter_value
            if not isinstance(tex, unreal.Texture2D) or name not in samp:
                continue
            key = (_pkg(tex), samp[name])
            if key in done:
                continue
            done.add(key)
            want = _PARAM_WANTS.get(name) or _SAMPLER_WANTS.get(samp[name])
            if not want:
                res["flags"].append("%s . %s: sampler %s not handled" % (mi.get_name(), name, samp[name]))
                continue
            ok_tc, set_tc, want_srgb = want
            changes = []
            if tex.get_editor_property("compression_settings") not in ok_tc:  # compression FIRST (see _fix_texture)
                changes.append("Compression %s" % set_tc.name)
                if fix: tex.set_editor_property("compression_settings", set_tc)
            if tex.get_editor_property("srgb") != want_srgb:
                changes.append("sRGB %s" % ("on" if want_srgb else "off"))
                if fix: tex.set_editor_property("srgb", want_srgb)
            if not changes:
                res["ok"] += 1
                continue
            res["textures_changed"].append("%s (%s on %s): %s" % (tex.get_name(), name, mi.get_name(), ", ".join(changes)))
            if fix:
                if tex.get_editor_property("srgb") != want_srgb:
                    res["errors"].append("%s: sRGB would not change to %s" % (tex.get_name(), want_srgb))
                eal.save_loaded_asset(tex, False)
    for mi in mis:  # textures changed -> refresh any open MI editor
        mel.refresh_material_instance_editor(mi)
    return res


def check_run():
    """Menu entry: selected MIs, or every MI under the selected folder(s)."""
    assets = _selected()
    mis = [a for a in assets if isinstance(a, unreal.MaterialInstanceConstant)]
    if not mis:
        for folder in _selected_folders():
            for p in eal.list_assets(folder, recursive=True, include_folder=False):
                a = unreal.load_asset(p.split(".")[0])
                if isinstance(a, unreal.MaterialInstanceConstant):
                    mis.append(a)
    if not mis:
        return _msg("Select material instances, or a folder of them, then click again.")
    res = check_textures(mis)
    lines = ["Checked %d material instance(s): %d texture(s) already right." % (res["checked"], res["ok"])]
    for key, title in [("textures_changed", "Texture settings FIXED + saved"), ("flags", "FLAGGED"), ("errors", "Errors")]:
        if res[key]:
            lines += ["", title + ":"] + ["  " + x for x in res[key]]
    if not res["textures_changed"]:
        lines.append("Nothing needed fixing.")
    _msg("\n".join(lines))


_target = None  # MI remembered by a click with only the MI selected (two-click flow)


def _selected():
    return unreal.EditorUtilityLibrary.get_selected_assets()


def _msg(text):
    unreal.log("Fill MI from Textures\n" + text)
    unreal.EditorDialog.show_message("Fill MI from Textures", text, unreal.AppMsgType.OK)


def run():
    """Menu entry. Either select the MI + its textures (or their folder) and click once, or
    click with ONLY the MI selected (remembered), then select the textures/folder and click again."""
    global _target
    assets = _selected()
    mis = [a for a in assets if isinstance(a, unreal.MaterialInstanceConstant)]
    if len(mis) > 1:
        return _msg("Select ONE material instance (found %d)." % len(mis))
    texs = _textures_from_selection(assets)
    if mis and not texs:
        _target = _pkg(mis[0])
        return _msg("Remembered %s.\n\nNow select its textures (or their folder) and click "
                    "Fill MI from Textures again." % mis[0].get_name())
    if not texs:
        return _msg("Nothing to do: select a material instance and/or its textures.")
    mi = mis[0] if mis else (unreal.load_asset(_target) if _target else None)
    if not mi:
        return _msg("No material instance: select the MI first (alone) and click, "
                    "then select the textures and click again.")
    _target = None
    _msg(report_text(fill(mi, texs)))
