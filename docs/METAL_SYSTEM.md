# ArchVault Metal Finish System

One master, a handful of shared finish maps, tint-driven instances. Any metal ×
any finish (polished, satin, matte, brushed, hammered, aged, oil-rubbed) from a
single shared texture library — no per-metal-per-finish texture sets.

**Why this works:** a clean metal's base color is effectively a flat tint
(brass vs. nickel vs. bronze is color + roughness, not unique albedo detail).
All the visual character of a finish lives in roughness, normal, and masks —
and those maps are metal-agnostic, so every metal shares them.

---

## 1. Metals do NOT pack (single-channel roughness + scalar M/AO)

Deliberate departure from `M_Opaque_Master`'s `Use Packed RMA` (R=rough,
G=metal, B=AO). Clean metals have **constant** metallic (1.0) and **constant**
material-scale AO (1.0) — so packing them would store two flat-white channels
for nothing. It also saves **zero samplers**: a lone roughness map is already a
single lookup, same as a packed one; you only save samplers by packing when the
other channels are real *maps*, and here they aren't. Scalar metallic/AO cost
no texture fetch at all.

So for metals:

| Channel role | Source                                   |
|--------------|------------------------------------------|
| Metallic     | **scalar param** (1.0); aging drops it   |
| AO           | **scalar param** (1.0); object AO = mesh-baked |
| Roughness    | **single-channel grayscale map** (only for brushed/hammered/worn) |

Texture import settings (enforced by
`archvault_metals.import_finish_textures()`):

- **Roughness maps (`*_R`):** single-channel — **Compression: Grayscale
  (TC_Grayscale)**, **sRGB OFF**. ~half the memory of a packed RGB mask.
- **Normal maps (`*_N`):** **Compression: Normalmap (TC_Normalmap)**, sRGB OFF.
- **Aging masks:** grayscale, sRGB OFF (reused from `/ArchVault/Textures/Alphas`).
- Tiling textures: 2K is plenty for hardware-scale finishes; power-of-two, seamless.

When would a metal genuinely need a metallic or AO *map*? Only composite "hero"
surfaces where metal and non-metal are baked into one texture — painted metal
chipping to bare metal, rust (a dielectric, metallic≈0), labels, worn coatings —
or deep cast relief wanting material-scale occlusion. Our system produces those
looks via the shader-side **aging layer** instead, so we never bake them. If you
ever hit a true composite hero metal, use `M_Opaque_Master` (which has the packed
RMA path) rather than bloating this master.

---

## 2. `M_Metal_Master` — parameter surface

Group / Parameter                | Type            | Default | Notes
---------------------------------|-----------------|---------|------------------------------------------
**Base**                          |                 |         |
Metal Tint                        | Vector          | Brass   | THE per-metal control (see §5 tint table)
Metallic                          | Scalar          | 1.0     | Rarely touched; aging pulls it down
AO                                | Scalar          | 1.0     | Constant; object occlusion = mesh-baked
**Finish**                        |                 |         |
Use Roughness Map                 | StaticSwitch    | false   | OFF = flat `Roughness` scalar (polished/satin/matte)
Roughness                         | Scalar          | 0.08    | Used when map is OFF — the whole finish for smooth metals
Finish Roughness                  | Texture (Gray)  | T_Finish_Brushed_R | Single-channel; used when map is ON
Roughness Min                     | Scalar          | 0.05    | Remap low end — the "finish dial" (map ON)
Roughness Max                     | Scalar          | 0.15    | Remap high end (map ON)
Use Finish Normal                 | StaticSwitch    | false   | OFF = flat normal (polished/satin/matte)
Finish Normal                     | Texture (Normal)| T_Finish_Brushed_N | Brushed / hammered / etc.
Normal Strength                   | Scalar          | 1.0     | FlattenNormal lerp
Use Anisotropy                    | StaticSwitch    | false   | ON for brushed finishes
Anisotropy Strength               | Scalar          | 0.6     | 0–1, drives the Anisotropy output pin
**Aging**                         |                 |         |
Use Aging                         | StaticSwitch    | false   | Gates the whole patina layer
Aging Mask                        | Texture (Gray)  | Grunge_Dirt_1 | From curated /ArchVault/Textures/Alphas
Aging Amount                      | Scalar          | 0.5     | Master intensity for the layer
Aged Tint                         | Vector          | dark brown | Target color where mask is white
Aged Roughness                    | Scalar          | 0.65    | Roughness where mask is white
Aged Metallic Drop                | Scalar          | 0.15    | Metallic reduced by mask*amount*this
**UVs**                           |                 |         |
(reuse `MF_AdvancedUV` / `MF_UVControl` exactly as in the other masters — Tiling, Offset, Rotation)

---

## 3. Node-by-node build (laptop session, UE open)

**Fastest path — build it programmatically:** run `import archvault_build_master;
archvault_build_master.build()` in the UE Python console. It clean-rebuilds
`M_Metal_Master` with every parameter and wire below, matching the exact names
`archvault_metals.py` expects. The manual steps here are the reference for what
that script constructs (and for hand-tweaks afterward).

Create `Material'/ArchVault/Masters/M_Metal_Master'`, Shading Model **Default
Lit**, and wire:

1. **UVs** — `MF_AdvancedUV` output feeds every texture sample (same pattern
   as `M_Opaque_Master`).
2. **Roughness** — `StaticSwitch(Use Roughness Map)`:
   - false → `Roughness` scalar directly (polished/satin/matte are uniform, no
     map or sample needed). This is the base roughness.
   - true → sample single-channel `Finish Roughness`, then
     `Lerp(Roughness Min, Roughness Max, sample)`. The remap turns one shared
     grayscale map into every finish level (brushed = 0.20–0.45, etc.).
3. **AO** — `AO` scalar param → Ambient Occlusion pin. Leave at 1.0; real
   object occlusion comes from the mesh's baked AO, not this tiling material.
4. **Metallic** — `Metallic` scalar param (1.0). Metals are metallic; the
   scalar keeps instances trivial and the aging layer drops it where needed.
5. **BaseColor** — `Metal Tint` vector param. Nothing else for clean metal.
6. **Finish Normal** — `StaticSwitch(Use Finish Normal)`:
   - true → sample `Finish Normal`, then FlattenNormal: `Lerp(float3(0,0,1),
     normalSample, Normal Strength)` → Normal pin.
   - false → constant `(0,0,1)`.
7. **Anisotropy** — `StaticSwitch(Use Anisotropy)`: true → `Anisotropy
   Strength` into the **Anisotropy** output pin (UE5 Default Lit supports it
   natively). Leave Tangent unconnected initially — mesh tangents follow the
   brushing direction on most hardware models; add a Tangent input later only
   if a specific asset needs rotated brushing.
8. **Aging layer** — `StaticSwitch(Use Aging)` wraps all three splices.
   `mask = AgingMaskSample.R * Aging Amount`, then:
   - BaseColor: `Lerp(MetalTint, Aged Tint, mask)`
   - Roughness: `Lerp(baseRoughness, Aged Roughness, mask)`
   - Metallic: `Metallic - mask * Aged Metallic Drop` (clamped 0–1)
   Same construction as the opaque master's Dirt/Grunge layer, so it will
   feel familiar in the graph.

Sampler budget: 3 texture samples worst-case (finish roughness, finish normal,
aging mask), **0 when polished/satin/matte** (all-scalar path — no samples at
all). The current unpacked MI_Metal uses 5+.

---

## 4. Shared finish library — `/ArchVault/Textures/Metals/Finishes/`

Metal-agnostic, seamless-tiling, ~2K. Shay authors single-channel grayscale
roughness maps (no packing). Polished/satin/matte need **no map at all** — they
run the scalar path. Target set is tiny — ~5 maps serve every metal:

| Asset                 | Type   | Used by                          |
|-----------------------|--------|----------------------------------|
| T_Finish_Brushed_R    | Gray   | Brushed (directional roughness streaks) |
| T_Finish_Brushed_N    | Normal | Brushed                          |
| T_Finish_Hammered_R   | Gray   | Hammered (roughness variation over dimples) |
| T_Finish_Hammered_N   | Normal | Hammered                         |
| T_Finish_Worn_R       | Gray   | Aged / Vintage / Oil-Rubbed base |
| Aging masks           | Gray   | Reuse curated `/ArchVault/Textures/Alphas` grunges — do **not** duplicate them here |

(Polished / Satin / Matte: no texture — `Use Roughness Map` OFF, `Roughness` scalar.)

Existing per-metal folders (`Brass/`, `Brass_Polished_4K/`, `Bronze_Clean_2K/`,
`Gold_Shiny/`, `Steek_Plain/`, `Iron_Raw/`) are retired once instances are
rebuilt — see §7.

---

## 5. Metal tints (linear RGB, measured metal albedos)

| Metal    | Metal Tint            | Aged Tint (suggested)  |
|----------|-----------------------|------------------------|
| Gold     | 1.000, 0.766, 0.336   | 0.45, 0.30, 0.10       |
| Brass    | 0.910, 0.778, 0.423   | 0.32, 0.22, 0.09       |
| Copper   | 0.955, 0.637, 0.538   | 0.20, 0.35, 0.30 (verdigris-ish) |
| Bronze   | 0.804, 0.498, 0.311   | 0.18, 0.12, 0.07       |
| Nickel   | 0.660, 0.609, 0.526   | 0.30, 0.28, 0.24       |
| Steel    | 0.560, 0.570, 0.580   | 0.22, 0.22, 0.23       |
| Iron     | 0.530, 0.510, 0.500   | 0.25, 0.13, 0.08 (rust lean) |
| Chrome   | 0.550, 0.556, 0.554   | 0.25, 0.25, 0.26       |

Enter as linear values in the vector param (UE color picker: use the RGB
fields, not the sRGB hex box). These live in `metal_manifest.json`; tweak
there and re-run the builder rather than editing instances by hand.

## 6. Finish recipes

Roughness column: a single value = scalar path (`Use Roughness Map` OFF); a
band = map path (grayscale `*_R` map remapped by Min/Max).

| Finish     | Roughness      | Rough Map     | Finish Normal | Aniso | Aging | Notes |
|------------|----------------|---------------|---------------|-------|-------|-------|
| Polished   | 0.08 (scalar)  | —             | off           | off   | off   | Mirror-adjacent; the default |
| Satin      | 0.22 (scalar)  | —             | off           | off   | off   | Newport Brass "satin" line |
| Matte      | 0.45 (scalar)  | —             | off           | off   | off   | |
| Brushed    | 0.20 – 0.45    | Brushed_R     | Brushed_N     | ON 0.6| off   | The D5-parity finish |
| Hammered   | 0.15 – 0.35    | Hammered_R    | Hammered_N    | off   | off   | Normal strength ~1.0 |
| Aged       | 0.25 – 0.55    | Worn_R        | off           | off   | ON 0.5| Worn_R + grunge mask |
| Vintage    | 0.30 – 0.60    | Worn_R        | Brushed_N 0.4 | off   | ON 0.65| Softer brushing + heavier aging |
| OilRubbed  | 0.40 – 0.65    | Worn_R        | off           | off   | ON 0.85| Aged Tint very dark brown (0.04, 0.03, 0.02); the classic ORB look |

Instance hierarchy (built by `archvault_metals.py`):

```
M_Metal_Master
└─ MI_Metal_Base                 (exposes everything, neutral steel)
   ├─ MI_Brass                   (tint set; finish = Polished defaults)
   │    ├─ MI_Brass_Brushed
   │    └─ MI_Brass_Aged
   ├─ MI_Nickel, MI_Bronze, ...  (same pattern)
```

Naming: `MI_<Metal>[_<Finish>]`. Per-finish children are created only for
combinations listed in the manifest's `build` section — don't pre-generate
all 64.

## 7. Workflow

On the laptop (UE open, after `git pull`):

```python
# UE Python console
import archvault_metals
archvault_metals.import_finish_textures(r"D:/path/to/authored/maps")  # optional
archvault_metals.build()          # creates/updates the whole MIC hierarchy
archvault_metals.build(dry_run=True)  # preview without touching assets

import archvault_audit
archvault_audit.report()                    # full audit, no changes
archvault_audit.fix_duplicate_alphas()      # dry-run list of dupe merges
archvault_audit.fix_duplicate_alphas(apply=True)  # consolidate + delete dupes
```

Cleanup order (matters — references first, deletion last):

1. Build `M_Metal_Master` (§3) and run `archvault_metals.build()`.
2. Re-point anything in projects that used the old `MI_Metal_*` instances.
3. Rename `Steek_Plain` → `Steel_Plain` **in the Content Browser** (in-editor
   rename fixes references; a git-level rename would break them).
4. `archvault_audit.report()` → delete retired metal texture sets and dupes
   only when their referencer count is zero.
5. Push via the ArchVault menu; other machines Pull.

## 8. Authoring roughness maps (for Shay)

You only need ~3 maps: `T_Finish_Brushed_R`, `T_Finish_Hammered_R`,
`T_Finish_Worn_R`. Polished/satin/matte need none.

- **Single-channel grayscale.** Just the roughness variation — no packing, no
  metallic channel, no AO channel. Export a grayscale PNG/TGA (or put it in one
  channel; the importer sets Grayscale compression + sRGB off).
- Bright = rougher, dark = smoother. The master's Min/Max remaps it into each
  finish's band, so author the *pattern* (streak direction, dimple falloff),
  not absolute values.
- Seamless tiling is non-negotiable for finish maps (they repeat on hardware).
- Don't bake metal color or metallic/AO into these — color comes from
  `Metal Tint`, metallic/AO are scalars.
- Gloss maps are just inverted roughness: invert once, save as the `_R` map,
  delete the Gloss source. Never ship both.
