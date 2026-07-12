"""
ArchVault library audit — find duplicate, redundant, and orphaned textures.

Read-only by default: report() prints findings and deletes nothing. The fix
functions only touch assets whose referencers have been checked — duplicates
with references are consolidated (references re-pointed to the keeper), and
nothing that is still referenced is ever deleted.

Usage (UE Python console, editor open):
    import archvault_audit
    archvault_audit.report()                       # full read-only audit
    archvault_audit.fix_duplicate_alphas()         # dry-run merge plan
    archvault_audit.fix_duplicate_alphas(apply=True)
    archvault_audit.delete_unreferenced(["/ArchVault/Textures/Metals/Gold_Shiny"], apply=True)

See docs/METAL_SYSTEM.md §7 for where this fits in the cleanup order.
"""
import unreal

_EAL = unreal.EditorAssetLibrary

ALPHAS = "/ArchVault/Textures/Alphas"
METAL_DIRS = ["/ArchVault/Textures/Metals", "/ArchVault/Textures/Iron_Raw"]

# Map-type suffixes that are dead weight in a metalness workflow.
REDUNDANT_TOKENS = ("_specular", "_height", "_displacement", "_scan1", "_preview")


def _list_assets(root):
    return [p.split(".")[0] for p in _EAL.list_assets(root, recursive=True, include_folder=False)]


def _name(path):
    return path.rsplit("/", 1)[-1]


def _referencers(path):
    return [r for r in _EAL.find_package_referencers_for_asset(path)
            if not r.startswith("/ArchVault/Textures")]  # texture-to-texture refs don't count


def _dupe_pairs(paths):
    """Pair suffix-convention names with their prefix-convention twins.

    'Brushed_Grunge' <-> 'Grunge_Brushed', 'BnW_Spots_1_Noise' <-> 'Noise_BnW_Spots_1'.
    Keeper is the prefix-style name (Grunge_*/Noise_*).
    """
    by_key = {}
    for p in paths:
        n = _name(p).lower()
        for token in ("grunge", "noise"):
            if n.startswith(token + "_"):
                by_key.setdefault((token, n[len(token) + 1:]), {})["keep"] = p
            elif n.endswith("_" + token):
                by_key.setdefault((token, n[: -(len(token) + 1)]), {})["drop"] = p
    return [(v["keep"], v["drop"]) for v in by_key.values() if "keep" in v and "drop" in v]


def report():
    """Print the full audit. Changes nothing."""
    unreal.log("=" * 60)
    unreal.log("ArchVault audit")
    unreal.log("=" * 60)

    # 1) Duplicate alphas (two naming conventions).
    alphas = _list_assets(ALPHAS)
    pairs = _dupe_pairs(alphas)
    unreal.log("-- Duplicate alphas: %d pairs (keep prefix-style, drop suffix-style)" % len(pairs))
    for keep, drop in pairs:
        refs = _referencers(drop)
        unreal.log("   drop %s  (referencers: %d)%s" %
                   (_name(drop), len(refs), "  <- consolidate first" if refs else ""))

    # 2) Redundant map types in metal folders (+ Gloss where a Roughness sibling exists).
    unreal.log("-- Redundant metal maps:")
    count = 0
    for root in METAL_DIRS:
        paths = _list_assets(root)
        names_lower = {p.lower() for p in paths}
        for p in paths:
            n = _name(p).lower()
            reason = None
            if any(t in n for t in REDUNDANT_TOKENS):
                reason = "unused map type (metalness workflow)"
            elif "gloss" in n and (p.lower().replace("gloss", "roughness") in names_lower
                                   or p.lower().replace("_gloss", "_rough") in names_lower):
                reason = "gloss duplicates sibling roughness"
            elif _name(p).startswith("TCom_"):
                reason = "duplicate source albedo (TCom_*)"
            if reason:
                count += 1
                refs = _referencers(p)
                unreal.log("   %s — %s (referencers: %d)" % (p, reason, len(refs)))
    if count == 0:
        unreal.log("   none found")

    # 3) Off-theme alpha sets.
    unreal.log("-- Off-theme alphas (delete if referencers = 0 and unused by you):")
    for p in alphas:
        n = _name(p)
        if n.startswith(("Plasma", "Crystal_", "MH_Particles", "Max_Hay_")):
            unreal.log("   %s (referencers: %d)" % (p, len(_referencers(p))))

    # 4) Fully unreferenced textures (informational — repo weight, not runtime cost).
    unrefd = [p for root in [ALPHAS] + METAL_DIRS
              for p in _list_assets(root) if not _referencers(p)]
    unreal.log("-- Unreferenced textures under Alphas/Metals: %d "
               "(safe to delete; recoverable from git history)" % len(unrefd))
    unreal.log("=" * 60)
    unreal.log("Nothing was modified. Use fix_duplicate_alphas()/delete_unreferenced() to act.")


def fix_duplicate_alphas(apply=False):
    """Merge naming-convention duplicates in the Alphas library.

    For each pair: if the suffix-style copy is referenced, consolidate it into
    the prefix-style keeper (re-points all references), then delete it.
    Dry-run unless apply=True.
    """
    pairs = _dupe_pairs(_list_assets(ALPHAS))
    if not pairs:
        unreal.log("No duplicate pairs found.")
        return
    for keep, drop in pairs:
        refs = _referencers(drop)
        if not apply:
            unreal.log("[dry-run] %s -> keep %s (%d refs to re-point)" %
                       (_name(drop), _name(keep), len(refs)))
            continue
        if refs:
            keeper = _EAL.load_asset(keep)
            dropped = _EAL.load_asset(drop)
            if not _EAL.consolidate_assets(keeper, [dropped]):
                unreal.log_warning("Consolidate failed for %s — skipped" % drop)
                continue
        elif not _EAL.delete_asset(drop):
            unreal.log_warning("Delete failed for %s — skipped" % drop)
            continue
        unreal.log("Merged %s -> %s" % (_name(drop), _name(keep)))
    if apply:
        unreal.log("Done. Save all (Ctrl+Shift+S), verify, then push via ArchVault menu.")


def delete_unreferenced(roots, apply=False):
    """Delete every asset under the given content paths that has zero referencers.

    Anything with referencers is skipped and reported. Dry-run unless apply=True.
    """
    for root in roots:
        for p in _list_assets(root):
            refs = _referencers(p)
            if refs:
                unreal.log("KEEP %s — %d referencer(s)" % (p, len(refs)))
                continue
            if not apply:
                unreal.log("[dry-run] would delete %s" % p)
            elif _EAL.delete_asset(p):
                unreal.log("Deleted %s" % p)
            else:
                unreal.log_warning("Delete failed for %s" % p)
