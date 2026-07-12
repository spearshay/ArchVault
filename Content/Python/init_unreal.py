"""
ArchVault startup script.

Adds a top-level "ArchVault" menu to the Unreal Editor main menu bar so the
library is always one click away in any project that has this plugin enabled.
Runs automatically on editor startup (requires the Python Editor Script Plugin).
"""
import os
import sys
import unreal

# Make this folder importable so menu commands can `import archvault_sync`.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.append(_THIS_DIR)

_SUBMENU = "LevelEditor.MainMenu.ArchVaultMenu"


def _build_menu():
    menus = unreal.ToolMenus.get()
    # Already added this session? Don't duplicate.
    if menus.is_menu_registered(_SUBMENU):
        return True
    main = menus.find_menu("LevelEditor.MainMenu")
    if not main:
        return False

    sub = main.add_sub_menu(main.menu_name, "", "ArchVaultMenu", "ArchVault",
                            "ArchVault material library")

    browse = unreal.ToolMenuEntry(name="ArchVault_Browse",
                                  type=unreal.MultiBlockType.MENU_ENTRY)
    browse.set_label("Browse ArchVault Library")
    browse.set_tool_tip("Jump the Content Browser to the ArchVault materials")
    browse.set_string_command(
        unreal.ToolMenuStringCommandType.PYTHON, "",
        "import archvault_menu; archvault_menu.browse()")
    sub.add_menu_entry("ArchVault", browse)

    master = unreal.ToolMenuEntry(name="ArchVault_OpenMaster",
                                  type=unreal.MultiBlockType.MENU_ENTRY)
    master.set_label("Open Master Material")
    master.set_tool_tip("Open the ArchVault master material in the Material Editor")
    master.set_string_command(
        unreal.ToolMenuStringCommandType.PYTHON, "",
        "import archvault_menu; archvault_menu.open_master()")
    sub.add_menu_entry("ArchVault", master)

    push = unreal.ToolMenuEntry(name="ArchVault_Push",
                                type=unreal.MultiBlockType.MENU_ENTRY)
    push.set_label("Push to GitHub  (commit + push)")
    push.set_tool_tip("Stage + commit local changes and push the library to GitHub")
    push.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, "",
                            "import archvault_sync; archvault_sync.push()")
    sub.add_menu_entry("Sync", push)

    pull = unreal.ToolMenuEntry(name="ArchVault_Pull",
                                type=unreal.MultiBlockType.MENU_ENTRY)
    pull.set_label("Pull from GitHub  (get latest)")
    pull.set_tool_tip("Pull the latest version of the library from GitHub")
    pull.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, "",
                            "import archvault_sync; archvault_sync.pull()")
    sub.add_menu_entry("Sync", pull)

    menus.refresh_all_widgets()
    unreal.log("ArchVault: registered top-level menu")
    return True


def _register():
    try:
        if _build_menu():
            return
    except Exception as e:
        unreal.log_warning("ArchVault menu: first attempt failed (%s); will retry" % e)

    # Menus may not be ready yet at startup -> retry on slate ticks until they are.
    state = {"handle": None}

    def _retry(delta_seconds):
        try:
            if _build_menu():
                unreal.unregister_slate_post_tick_callback(state["handle"])
        except Exception:
            unreal.unregister_slate_post_tick_callback(state["handle"])

    state["handle"] = unreal.register_slate_post_tick_callback(_retry)


_register()
