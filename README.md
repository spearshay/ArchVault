# ArchVault

Centralized base asset library for Unreal Engine — a **content-only plugin** holding master materials, material instances, material functions, and shared textures. Drop it into any UE project's `Plugins/` folder and its assets mount at a stable path (`/ArchVault/...`), so references never break across projects or machines.

## Structure

```
Content/
  Masters/      Master materials (M_Master_Arch opaque, M_Master_Glass, M_LandscapeMaterial_HQ)
  Functions/    Shared material functions (MF_PSR UV transform, randomization, etc.)
  Instances/    Material instances by type (Metal, Wood, Marble, Concrete, Glass, ...)
  Textures/     Shared texture maps
```

## Install

### Prerequisites (one time per machine)

- **Unreal Engine 5.7** (or newer).
- **Git** and **Git LFS**. After installing Git LFS, run it once:
  ```bash
  git lfs install
  ```
  This is required: the asset files (`.uasset`, textures, etc.) are stored via Git LFS. A plain clone *without* LFS pulls down small pointer files instead of the real assets, and the materials will fail to load in Unreal.

### Option A — clone into a project (keeps version history)

```bash
cd <YourProject>/Plugins
git clone https://github.com/spearshay/archvault.git ArchVault
```

The folder **must** be named `ArchVault` so assets mount at the stable `/ArchVault/...` path and references don't break.

### Option B — copy the folder (simplest for non-developers)

Copy the `ArchVault` plugin folder into `<YourProject>/Plugins/ArchVault`. Make sure you copy from a checkout where LFS content was actually pulled (real assets, not pointer files) — otherwise clone with LFS instead.

### Enable it

1. Open the project. ArchVault **auto-enables** (`"EnabledByDefault": true`), or enable it manually in **Edit → Plugins → Asset Library → ArchVault** and restart.
2. Assets appear in the Content Browser under the **ArchVault** root.

## Sharing with others

ArchVault is a self-contained, content-only plugin — it works in any UE 5.7+ project on any machine, for you or anyone else. To share it:

- **With repo access:** they clone it exactly as in Option A (needs read access to `spearshay/archvault`).
- **Without git:** zip the `ArchVault` folder (with real LFS assets pulled down) and send it; they drop it into `Plugins/`.

This project is released under the **MIT License** (see [`LICENSE`](LICENSE)), so others are free to use, copy, and modify it.

## Metals workflow

Metals use a dedicated master (`M_Metal_Master`) with a shared, metal-agnostic
finish library — any metal × finish combo (polished, brushed, aged, oil-rubbed,
…) comes from tints + ~5 shared grayscale maps (metallic/AO are scalars, not
packed), not per-combination texture sets. Full build spec and workflow:
[`docs/METAL_SYSTEM.md`](docs/METAL_SYSTEM.md).

- `Content/Python/archvault_metals.py` — builds the `MI_Metal_Base → MI_<Metal>
  → MI_<Metal>_<Finish>` instance hierarchy from `metal_manifest.json`. Edit the
  manifest, re-run `archvault_metals.build()`; don't hand-edit instances.
- `Content/Python/archvault_audit.py` — read-only library audit
  (`archvault_audit.report()`): duplicate alphas, redundant maps, orphans; with
  reference-safe fix/delete helpers.

## Version control

Binary assets are tracked with **Git LFS** (see `.gitattributes`). Because UE assets are binary and **cannot be merged**, treat edits as **lock-based / sequential** across machines and collaborators (`git lfs lock` if a remote with locking is used). Read-and-use by many people in parallel is fine; simultaneous *editing* of the same asset is what to coordinate — if two people edit and both push, one set of changes is overwritten.

## Engine

Built for Unreal Engine 5.7.
