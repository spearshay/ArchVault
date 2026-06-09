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

## Usage

1. Clone/copy this repo into `<YourProject>/Plugins/ArchVault`.
2. Enable **ArchVault** in the project's `.uproject` (or it auto-enables — `EnabledByDefault`).
3. Assets appear in the Content Browser under the **ArchVault** root.

## Version control

Binary assets are tracked with **Git LFS** (see `.gitattributes`). Requires `git lfs install` once per machine. Because UE assets are binary and cannot be merged, treat edits as **lock-based / sequential** across machines (`git lfs lock` if a remote with locking is used).

## Engine

Built for Unreal Engine 5.7.
