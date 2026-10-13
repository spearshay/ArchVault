"""
ArchVault Git sync — push/pull the library from inside the Unreal Editor.

Called by the "ArchVault" editor menu entries (see init_unreal.py).
Runs git as a subprocess against this plugin's own folder (the Git repo),
so it works regardless of where the plugin is installed on a given machine.
"""
import os
import socket
import datetime
import subprocess
import unreal


def _repo():
    # .../ArchVault/Content/Python/archvault_sync.py -> .../ArchVault
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


_GIT = None
def _git_exe():
    for cand in ("git", r"C:\Program Files\Git\cmd\git.exe"):
        try:
            subprocess.run([cand, "--version"], capture_output=True, text=True, timeout=20)
            return cand
        except Exception:
            continue
    return "git"


def _git(args, timeout=600):
    global _GIT
    if _GIT is None:
        _GIT = _git_exe()
    return subprocess.run([_GIT, "-C", _repo()] + list(args),
                          capture_output=True, text=True, timeout=timeout)


def _dialog(title, message):
    try:
        unreal.EditorDialog.show_message(title, message[:2000], unreal.AppMsgType.OK)
    except Exception:
        unreal.log("%s: %s" % (title, message))


# ArchVault is authored in UE 5.6 (matches Gustavo, 2026-10). An asset saved by a newer engine can't be opened by
# an older one, so a push from 5.7/5.8 would silently break the library for every 5.6 user.
AUTHORING_VERSION = "5.6"


def push():
    """Stage everything, auto-commit if there are changes, and push to GitHub."""
    ver = unreal.SystemLibrary.get_engine_version()
    if not ver.startswith(AUTHORING_VERSION + "."):
        _dialog("ArchVault — Push blocked",
                "ArchVault is authored in UE %s; this editor is %s.\n\nAssets saved here can't be opened by %s. "
                "Make the change in %s and push from there." % (AUTHORING_VERSION, ver.split("-")[0],
                                                                AUTHORING_VERSION, AUTHORING_VERSION))
        return
    unreal.log("ArchVault: push starting (" + _repo() + ")")
    _git(["add", "-A"])
    changed = _git(["status", "--porcelain"]).stdout.strip()
    if changed:
        host = socket.gethostname()
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        _git(["commit", "-m", "ArchVault update from %s (%s)" % (host, stamp)])
    res = _git(["push"])
    out = (res.stdout + res.stderr).strip()
    if res.returncode == 0:
        _dialog("ArchVault — Pushed", ("Library pushed to GitHub.\n\n" + out) if out else "Library pushed to GitHub (nothing new).")
    else:
        _dialog("ArchVault — Push FAILED", out or "Unknown git error")


def pull():
    """Pull the latest library from GitHub."""
    unreal.log("ArchVault: pull starting (" + _repo() + ")")
    res = _git(["pull"])
    out = (res.stdout + res.stderr).strip()
    if res.returncode == 0:
        _dialog("ArchVault — Pulled", (out + "\n\nIf assets changed, restart the editor to load them.") if out else "Already up to date.")
    else:
        _dialog("ArchVault — Pull FAILED", out or "Unknown git error")
