"""
ArchVault menu actions — Content Browser navigation for the editor menu.

Called by the "ArchVault" editor menu entries (see init_unreal.py). Lives in a
uniquely-named module (NOT init_unreal) so the menu's click-time
`import archvault_menu` always resolves to THIS plugin's code. The module name
`init_unreal` is shared by every plugin's startup script and collides in
sys.modules, so routing clicks through it raised
`module 'init_unreal' has no attribute 'browse'`. Mirrors archvault_sync.
"""
import unreal


def browse():
    """Reveal the ArchVault library in the Content Browser.

    Dynamic (resolves assets at click time) so it survives renames/reorg —
    syncs to the master materials, falling back to any ArchVault asset.
    """
    assets = unreal.EditorAssetLibrary.list_assets(
        "/ArchVault/Masters", recursive=False, include_folder=False)
    if not assets:
        assets = unreal.EditorAssetLibrary.list_assets(
            "/ArchVault", recursive=True, include_folder=False)[:1]
    if assets:
        unreal.EditorAssetLibrary.sync_browser_to_objects([a.split(".")[0] for a in assets])
    else:
        unreal.log_warning("ArchVault: no assets found under /ArchVault to browse.")


def open_master():
    """Open an ArchVault master material (prefers the opaque master)."""
    prefer = ["/ArchVault/Masters/M_Opaque_Master", "/ArchVault/Masters/M_Metal_Master"]
    target = next((p for p in prefer if unreal.EditorAssetLibrary.does_asset_exist(p)), None)
    if target is None:
        masters = unreal.EditorAssetLibrary.list_assets(
            "/ArchVault/Masters", recursive=False, include_folder=False)
        target = masters[0].split(".")[0] if masters else None
    if target is None:
        unreal.log_warning("ArchVault: no master material found under /ArchVault/Masters.")
        return
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets(
        [unreal.load_asset(target)])
