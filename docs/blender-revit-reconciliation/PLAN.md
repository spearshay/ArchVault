# Blender → Revit Documented-Data Reconciliation Toolkit — Planning & Architecture

**Status: PLANNING ONLY. No production code in this pass.** This document is the
reasoned-out architecture and build plan, ready to execute when Shay frees up.

**Author context:** Shay Spear (viz/archviz, Blender 5.1, Oregon) feeding clean,
placeable data to Vinny (Revit 2025/2026 BIM lead, Arizona) at Craydl. Decision
maker is Adam (sales/owner, reverses scope mid-project).

---

## 0. How this plan was grounded (and an honest gap)

The brief asked me to ground everything in real machine state. Important caveat
up front, stated plainly:

- **The `ArchVault` git repo this ran in is the *Unreal* side of the pipeline** — a
  content-only UE plugin (master materials `M_Master_Arch`, instances `MI_*`,
  functions `MF_*`, a `Content/Python/archvault_sync.py` git-sync menu). The
  Blender `.blend` files, the LFG tool, and prior session logs are **not on this
  machine.** This plan lives in this repo only because that is the branch I was
  pointed at.
- I therefore grounded against the **real connected sources** instead, which is
  arguably better than the local blend files: Google Drive (the Craydl reference
  docs, the LFG project notes, the 61st job dossier notes, and the **existing
  `craydl_revit_pipeline_addon.py` source**), the Miro board index (Job Flow, LFG,
  61st-Interior/Exterior, Viz Outliner, CRAYDLOPS), and **Autodesk's official Revit
  help** for the coordinate-system and import-path unknowns.
- **What I could not do:** open the 225 MB `SIXTY-FIRST_(BEDROCK)_WIP A.blend` on
  Drive and inspect the actual can-light / wall / soffit objects. The per-element
  data model below is therefore built from the *documented* structure of those
  files (naming, collection, and convention notes) and must be **verified against
  the live blend as build-step zero of v1.** That verification is cheap and is
  written into the plan.

Everything below cites where each constraint came from so it can be re-checked.

---

## 1. The problem & where this toolkit fits

Visualization happens **outside** Revit (Blender + D5); construction documentation
must live **inside** Revit. When a design decision is authored on the viz side and
later needs documentation, capturing it back into Revit is a manual, error-prone
reverse round-trip.

The team's larger architecture is already decided: a **split-source D5 workflow** —
Vinny LiveSyncs the authoritative Revit model *in*; Shay links Blender-authored
hero/detail assets into the same D5 project. Governing rule: **every element is
authored in exactly one place** ("author-once"). Documented geometry → Revit
(Vinny); viz-only craft → Blender (Shay); gray-zone items assigned to one side per
project, up front.

> Grounding note: the literal phrase "author-once" is **not** in the Drive docs —
> it's the brief's coinage for an *implicit* rule. The docs do establish the
> ownership split verbatim: *"Vinny = all technical drawings and construction
> documents; Shay = renders only — never conflate these roles"* and *"the primary
> production handoff is Vinny → Shay via FBX export from Revit"*
> (`CRAYDL_REF_03_WORKING_CONTEXT.md`). The forward handoff today is **one-way,
> Revit → Blender.** There is currently **no** Blender → Revit write-back path. This
> toolkit is net-new and is the reverse complement of that forward flow.

**This toolkit is the escape hatch for when author-once is broken by circumstance**
— something authored in Blender as viz-only gets promoted to "needs docs" partway
through (exactly the 61st case). It is *not* a general Blender→Revit converter and
should never try to be; it extracts **reconstruction data for a curated handful of
promoted elements**, in a form Vinny can place with minimal rework.

---

## 2. Observed state that shapes the design (the findings that matter)

These are the concrete discoveries that change the architecture. Each is a
constraint, not a preference.

### 2.1 There is already a Craydl Blender↔Revit addon — match it, don't reinvent
`craydl_revit_pipeline_addon.py` (on Drive) is a working Blender **4.2** addon. Its
shape is the template this toolkit must follow for coexistence and maintainability:

- A **View3D → N-panel** under `bl_category = "Craydl"`. *The reconciliation tool
  should add its panel to the **same** "Craydl" tab*, not a new one.
- The addon is a **thin UI shell**; the real work lives in standalone scripts
  (`revit_fbx_cleanup.py`, `fixture_swap.py`) that the addon loads at runtime,
  **injecting config globals** (`DRY_RUN`, `SCOPE`, `RUN_STAGES`) and capturing
  `stdout` as a human-readable report. Quote: *"The source scripts are the single
  source of truth; this only injects settings."*
- Safety patterns to reuse verbatim: `DRY_RUN` defaults **True**; destructive runs
  go through `invoke_confirm`; a **`SCOPE` enum (all / selection / collection)** +
  a `source_collection` pointer so tools can run on *worked* files without
  disturbing hand-sorted work; `AddonPreferences` holds the scripts folder.

**Architectural decision:** the reconciliation toolkit ships as **(a) a standalone
extractor script** (`revit_reconcile_export.py`, config-global driven, the source of
truth) **plus (b) a panel registered into the existing Craydl addon** (or a sibling
addon that adds to the same tab). This guarantees coexistence with LFG and the
cleanup pipeline and reuses the DRY_RUN / SCOPE / report idioms Shay already
maintains.

### 2.2 The cleanup pipeline DESTROYS Revit element identity — ordering hazard
The existing cleanup addon has a `clean_names` stage described as *"Strip Revit IDs
/ fix names."* Revit-origin geometry arrives (via the Max round-trip, see 2.4)
with object names that **embed the Revit element identity**, and the cleanup wipes
them. The cleanup also offers **`join` ("merge Walls/Floors into single meshes",
DESTRUCTIVE)** which collapses per-element identity entirely.

**Consequence (first-class):** reconciling a *moved existing Revit element* back to
its Revit twin requires the original Revit element ID/UniqueId. That data is only
present **before** `clean_names`/`join` run. So either:
- the toolkit captures the Revit ID into a stable custom property **at import time
  / before cleanup**, or
- reconcile-bound elements are kept in a collection that cleanup's `SCOPE` excludes.

This is the single most important interaction with existing tooling.

### 2.3 The 61st reality is messier than "extract the can lights"
From `bedbrock-61st-job.md` (the live job memory):
- **The current approved RCP has ZERO can lights.** Quote: *"Current RCP = Phil's
  Jun 8 JobTread version (Paulina approved Jun 9; Drive + Miro copies STALE) — it
  has ZERO can lights (sconce/flushmount/pendant/heater only)."* So the can lights
  Shay built in Blender as viz are exactly the elements that **diverge from the
  latest documented design.** That both *justifies* a reconciliation tool **and
  warns** it must not blindly document fixtures the design has since dropped.
  → Reconciliation must surface **"this exists in viz but not in the current
  RCP"** as a first-class state, and the human confirms intent before export.
- **Vinny split the Revit model arch-vs-ID.** Quote: *"Shay testing arch-vs-ID
  model split ('TEST IDEA' part1/part2 FBX)"*, main export
  `SIXTY-FIRST(BEDROCK)_MAIN.fbx`. Walls/soffits live in the **arch** file;
  millwork/fixtures in the **ID** file. → Every extracted element must record
  **which Revit file it targets**, or Vinny gets noise in the wrong model.
- **Currency risk is structural, not incidental.** Quote: *"JobTread is the comms
  hub and leaks to Drive… Current design docs (incl. RCPs) often live ONLY in
  JobTread messages, newer than Drive/Miro copies."* → The tool's output must be
  timestamped and state which RCP/model version it was reconciled against.

### 2.4 Coordinate & unit facts already established in the pipeline
- Blender scene: **display = Imperial/Inches, internal = meters** (`IN = 0.0254`);
  *"Verify all world positions via `matrix_world`"* (`REF_04_PIPELINE_D5.md`). So
  the extractor reads `obj.matrix_world` → **meters**, no display-unit ambiguity.
- **Both Blender and Revit are Z-up** → no axis swap on Blender→Revit (unlike the
  Blender→UE path, which needs orientation conversion). This makes the reverse
  direction *simpler* than the forward one.
- Inbound Revit data takes a **3ds Max round-trip** (`raw Revit FBX → 3ds Max live
  Revit link → re-export FBX → Blender`) to preserve materials/names; FBX carries a
  **0.01 unit scale** quirk (`craydl-blender-pipeline.md`). This matters for
  *imported* geometry's baked transforms, but the extractor sidesteps it by reading
  live `matrix_world` at export time.
- **Revit internal unit = feet**, but **Dynamo geometry nodes operate in meters**
  (Autodesk: relocate/place *"based on specific coordinates in meters"*). So a
  Blender export in meters feeds a Dynamo importer with **no conversion** if it
  places via `Point.ByCoordinates`; only a raw-API placement needs `÷ 0.3048`.

### 2.5 LFG is a sellable pendant generator, NOT the can-light mechanism
`lfg-project.md` is explicit: **LFG = a procedural *pendant* light product** for
Blender Market/Gumroad. It does **not** place recessed/can lights in project scenes.
So LFG is not the can-light data source — but its **conventions are the house style
to mirror**:
- Typed node-group prefix `GN_LFG_*`; *"keep EVERYTHING a modifier parameter."*
- **Serialize tool state to JSON** ("serialize assembler modifier inputs to JSON →
  re-editable/reconstructable/shareable") — direct precedent for a JSON export
  schema.
- A **dropzone collection** (`LFG_REF`) as the canonical hand-off bucket — direct
  precedent for a `needs-docs` collection.
- Asset-Browser `obj.asset_mark()` + 512² previews; author "Shay Spear / Craydl".

### 2.6 Trim / casing / millwork tooling already exists (61st relevance)
`blender-tools-portfolio.md`: there is **door-casing automation** ("trace panel
silhouette, place at interior wall face, offset 0.5″ reveal, bevel-object sweep")
and a **profile-curve library** with strict origin conventions ("mouldings in XY,
origin at wall-floor corner, +X away from wall; arches in XZ, origin at springline
center; names carry dimensions"). Note the quirk **"Revit doors float 6″"** — a
real Z-offset gotcha for anything hosted to doors. These are the 61st millwork
elements that may need docs in later phases; their origin conventions are already
defined and the extractor should honor them rather than invent new ones.

---

## 3. The hard problem, first: coordinate & unit alignment

Exports are worthless if coordinates don't land in Revit. Treated as the primary
design problem.

### 3.1 The core difficulty
Blender's project origin and Revit's reference points are unrelated. Revit has
**four** reference frames an importer can target (Autodesk confirms all four are
selectable in Dynamo): **Internal Origin, Project Base Point (PBP), Survey Point,
Shared Coordinates.** PBP and Survey can be moved/unclipped and *do* drift
(Autodesk has whole support articles on PBP shifting after a Transfer Project
Standards). Picking the wrong frame, or one that moves, silently misplaces
everything.

### 3.2 Recommended strategy: a single agreed **anchor datum**, keyed to Internal Origin
1. **Choose one shared, immovable reference frame: Revit Internal Origin.** It never
   moves, is identical across Vinny's split files (arch + ID share the same Revit
   internal origin when they were modeled together), and Dynamo can read/write it
   directly. PBP/Survey are explicitly *not* used as the math anchor (they drift).
2. **Establish a known anchor point present in BOTH worlds.** Per Autodesk's
   Shared-Coordinates guidance, pick a *characteristic point* — a building
   gridline intersection or a specific building corner — that exists in Vinny's
   Revit model *and* is identifiable in Shay's Blender scene (it came in via the
   same FBX). Call it **`ANCHOR`**.
3. **Record the anchor once per project** as: its Blender world coordinate
   (`matrix_world` translation, meters) and its Revit Internal-Origin coordinate
   (feet or meters, from Vinny). The difference is a **pure translation** (because
   both are Z-up and the FBX import did not rotate the plan — to be *verified* in
   build-step zero). No rotation, no scale beyond unit conversion if the FBX import
   left one in.
4. **Export every element relative to `ANCHOR`** (`P_blender − ANCHOR_blender`, in
   meters). The Dynamo importer adds `ANCHOR_revit` back. This makes the export
   **origin-independent and robust to the model split** — both Revit files share
   the anchor.
5. **Carry units explicitly** in the export header (`"units": "m"`,
   `"up_axis": "Z"`, `"anchor_blender": [...]`, `"reconciled_against": "<RCP/model
   version + date>"`). The importer converts m→ft only if it places via raw API.

### 3.3 Verification gate (non-negotiable, build-step zero)
Before trusting any extractor, run a **round-trip calibration on one known
element**: pick a fixture/corner that exists in *both* Vinny's Revit and Shay's
Blender, export it, place it via the importer, and have Vinny confirm it lands on
top of the original. Until that passes, no real data ships. (This mirrors the
existing pipeline habit: *"import the test asset, measure it… confirm scale,"* and
*"read scene data via MCP — never trust screenshots."*)

> **Open decision for Vinny (see §10):** which characteristic point is the anchor,
> and what is its Internal-Origin coordinate in each of the two split files.

---

## 4. The "needs-docs" tagging mechanism

Requirements: survives the author-once workflow, is **hard to apply by accident**,
survives save/reload, and coexists with LFG and the cleanup addon.

### 4.1 Recommendation: a custom property as the source of truth, a collection as the UI
Use **both**, with the custom property authoritative:

- **Authoritative tag = an object custom property** `craydl_docs` (a small dict-ish
  set of string props): `craydl_docs_state` ∈ `{needs_docs}`, plus
  `craydl_docs_kind` ∈ `{new, moved, viz_only}` (see §6),
  `craydl_docs_eltype` ∈ `{can_light, wall, soffit, casing, …}`, and optional
  `craydl_revit_id` (captured before cleanup, §2.2). Custom properties **persist in
  the .blend, survive append/link, and cannot be set by a stray click** — they only
  exist if a tool wrote them. This is the "hard to apply by accident" guarantee.
- **UI/visibility convenience = a dedicated collection** `DOCS_REVIEW` (mirroring
  LFG's `LFG_REF` dropzone idiom). The "Tag selection as needs-docs" operator both
  writes the custom properties **and** links the objects into `DOCS_REVIEW`. The
  collection is how a human eyeballs the doc set; the properties are how the
  exporter finds and classifies it. If the two disagree, the exporter trusts the
  property and warns.

**Why not naming convention as the tag?** Naming is the *least* durable choice here:
the cleanup pipeline actively **renames objects** (`clean_names`), so a name-based
tag would be silently stripped. Rejected for that reason. (Naming is still used for
*human* legibility, not as the machine tag.)

### 4.2 Interaction with author-once
Tagging is the explicit, deliberate act of saying "this Blender-authored element is
being *promoted* to needs-docs." The operator should require the user to pick the
`kind` (new / moved / viz_only-confirm) at tag time, so promotion is a conscious
classification, not a default. `viz_only` is taggable too — to positively mark
"reviewed, stays viz-only, do **not** document," so the exporter can prove the doc
set is complete rather than guessing at silence.

---

## 5. Data model per element type

General envelope (JSON, one record per element), then type-specific payloads. JSON
chosen as the internal schema (LFG precedent; lossless; trivially convertible to the
CSV the Dynamo importer eats — see §7).

```jsonc
{
  "schema": "craydl.reconcile/v1",
  "exported": "2026-06-21T14:00:00Z",
  "blender_file": "SIXTY-FIRST_(BEDROCK)_WIP A.blend",
  "units": "m",
  "up_axis": "Z",
  "anchor": { "name": "GRID_A1_corner",
              "blender_m": [x, y, z] },        // §3 datum
  "reconciled_against": "RCP Phil 2026-06-08 (JobTread)",
  "target_revit_file": "arch" | "interior_design",
  "elements": [ /* records below */ ]
}
```

Common per-element fields: `id` (stable uuid), `name` (human), `eltype`,
`kind` (new/moved/viz_only), `revit_id` (nullable), `pos_rel_anchor_m` ([x,y,z]),
`notes`.

### 5.1 Can / recessed lights (v1 priority)
What Vinny needs to place a face-based/ceiling-hosted family (validated against
Autodesk's lighting-fixture placement docs):

| Field | Source in Blender | Why Vinny needs it |
|---|---|---|
| `pos_rel_anchor_m` [x,y,z] | `matrix_world` translation − anchor | XY = plan location; Z = mounting height reference |
| `ceiling_ref` | nearest ceiling/host plane Z, or named room | Face-based families **must host to a real ceiling**; placement fails with no ceiling in view |
| `room` | collection / room bounds | Which RCP room/zone it belongs to |
| `type` | object name / custom prop | Fixture type/family (e.g. 4″ recessed, wall-wash) |
| `spacing_group` | derived: collinear/grid clusters | Lets Vinny array rather than place one-by-one |
| `switching` | **human-entered** custom prop | Switch leg / control zone — *not derivable from geometry* |
| `count_in_group` | derived | Sanity check vs RCP |

**Placement-path caveat (Autodesk-confirmed):** face-based lighting families hosting
to a **linked** model's ceiling are fragile — they attach to the wrong face / come
in upside-down, and *"cannot be rotated vertically."* **Therefore the v1 deliverable
is positions-as-data for Vinny to host in his own model**, not auto-hosted instances
pushed across a link. Orientation (aim) is only relevant for adjustable/wall-wash
cans; capture it from the object's local −Z only when present.

### 5.2 Moved / added walls & soffits (phase 2)
Wall data model (validated against Revit's wall properties + Dynamo `Wall.ByCurve`):

| Field | Source | Revit meaning |
|---|---|---|
| `centerline` [[x,y,z],[x,y,z]] rel anchor | wall mesh principal axis at base | `Location Line = Wall Centerline`; the curve `Wall.ByCurve` consumes |
| `base_level` / `base_offset_m` | min-Z of element vs known level Zs | Base Constraint + Base Offset |
| `height_m` | bbox Z extent | Unconnected Height (or Top Constraint level) |
| `thickness_m` | mesh cross-section / wall-type lookup | Selects/!matches the Revit wall **Type** (type carries thickness) |
| `kind` | new vs moved (§6) | new wall vs delta on an existing one |
| `delta_vs_original_m` | current centerline − original Revit-import centerline | For *moved* walls: the vector Vinny applies |
| `revit_id` | captured pre-cleanup (§2.2) | Which existing wall to move |

Soffits are modeled as a wall/ceiling hybrid: capture **footprint polyline +
bottom Z + thickness/height**; flag `eltype: soffit` so Vinny builds them as
bulkheads, not walls. Wall **classification** (interior vs exterior) can reuse the
existing `blender-wall-interior-exterior-classify` ray method (noted in Drive; read
it before building phase 2).

### 5.3 Trim / casing / millwork (phase 3, only if worth it)
Defer. If pursued, **reuse the existing profile-curve origin conventions** (§2.6)
and the door-casing automation's data rather than re-deriving. Honor "Revit doors
float 6″." Likely delivered as **profile + path polyline + reveal offset**, not
solids — but only if Vinny confirms viz-fidelity trim is worth documenting at all
(it usually is a Revit *detail-component* decision, not a model decision).

---

## 6. Reconciliation awareness: new / moved / viz-only

Vinny must not be handed noise. Three states, set at tag time and refined by the
exporter:

- **`new`** — authored in Blender, no Revit twin. Export full reconstruction data.
- **`moved`** — a Revit-origin element (has a captured `revit_id`) whose transform
  changed in Blender. Export the **delta** vs the original imported transform, not
  absolute geometry. *Requires* the pre-cleanup ID capture from §2.2.
- **`viz_only`** — positively marked "do not document." Excluded from export but
  **counted**, so the handoff can assert completeness.

The exporter additionally computes a **divergence flag** against the current RCP/
model where possible (the 61st "viz has cans, RCP has none" case): an element can be
`new` *and* `not_in_current_rcp`, which the report shows so the human confirms intent
before it reaches Vinny. Detecting "moved" automatically needs the original import
transform; the practical mechanism is to **snapshot `matrix_world` + `revit_id` into
a custom property at import time** (a tiny addition to the existing cleanup flow, or
a one-button "baseline" pass), so a later compare yields the delta.

---

## 7. Output format & the Vinny-side Revit import path

**This is the highest-leverage unknown and a human decision (Vinny owns it).** The
chosen import path dictates the export format. Recommendation with alternatives:

### 7.1 Recommended: **CSV ⇄ Dynamo** (`Data.ImportCSV` → `FamilyInstance.ByPoint` / `Wall.ByCurve`)
- **Why:** Autodesk documents the exact round-trip — Dynamo reads CSV point lists
  and places/relocates elements *"based on specific coordinates in meters,"* and the
  reverse (Revit→CSV) is a stock workflow. It is the lowest-friction, most
  inspectable, most *sustainable* option — Vinny can open the CSV, see the numbers,
  and a Dynamo graph is maintainable by a BIM lead without bespoke software.
- **Format:** the toolkit emits **JSON (canonical, lossless) + a flattened CSV per
  element type** (one CSV for cans: `name,x,y,z,type,ceiling_ref,room,switching,
  group`; one for walls: `name,x1,y1,z1,x2,y2,z2,base_level,base_offset,height,
  thickness,kind,revit_id,delta_x,delta_y`). Coordinates are **meters relative to
  ANCHOR**; the Dynamo graph adds the anchor and converts units.
- **Deliverables to build:** the Blender exporter **and** a small, version-pinned
  **Dynamo graph** (`craydl_place_cans.dyn`, `craydl_place_walls.dyn`) that Vinny
  keeps. The graph is part of the toolkit, not Vinny's problem to invent.

### 7.2 Alternatives (document, don't build first)
- **IFC link (BlenderBIM/IfcOpenShell):** Blender→IFC→Revit *link*. Cleaner for
  geometry-rich elements (walls/soffits) and round-trips coordinates well, but
  produces a *linked reference*, not native placeable families, and is heavier to
  set up. Good candidate for **phase-2 walls** if CSV+Dynamo proves clumsy for
  geometry. (Autodesk notes Dynamo IFC export can target a chosen reference point —
  same anchor discipline applies.)
- **Direct shared-coordinates DWG/FBX underlay:** export a positioned underlay Vinny
  traces over. Lowest tech, highest manual effort. Fallback only.
- **Revit schedule / parameter CSV import:** only relevant if the "data" is
  tabular (e.g. switching schedules), not positional. Not a placement path.

> The format is **deliberately decoupled** behind the JSON canonical schema so that
> if Vinny's answer in §10 is "I prefer IFC" or "I already have a family-placement
> macro that eats *this* CSV layout," only the thin export-adapter changes, not the
> extractors.

---

## 8. Module architecture

Mirrors the existing addon's "thin UI over source-of-truth scripts" shape.

```
craydl-reconcile/
  revit_reconcile_export.py      # SOURCE OF TRUTH script (config globals, no UI)
    ├─ config globals: DRY_RUN, SCOPE, SOURCE_COLLECTION, ANCHOR, TARGET_FILE,
    │                  ELEMENT_TYPES, OUTPUT_DIR, RECONCILED_AGAINST
    ├─ tagging:    tag_needs_docs(objs, kind, eltype)  -> writes custom props + DOCS_REVIEW
    │              capture_baseline(objs)              -> snapshot matrix_world + revit_id
    ├─ core:       collect_tagged()  -> [obj]          (reads custom props, honors SCOPE)
    │              anchor_relative(obj) -> [x,y,z] m   (matrix_world − ANCHOR)
    │              classify(obj) -> new|moved|viz_only (uses baseline if present)
    ├─ extractors (registry, one per eltype — extensible):
    │              extract_can_light(obj)  -> record
    │              extract_wall(obj)        -> record   (phase 2)
    │              extract_soffit(obj)      -> record   (phase 2)
    │              extract_casing(obj)      -> record   (phase 3, optional)
    ├─ reconcile:  divergence_report(records, rcp_ref) -> flags
    └─ writers:    write_json(records); write_csv(records, eltype)
  panel_reconcile.py             # registers into the existing "Craydl" N-panel tab
  dynamo/
    craydl_place_cans.dyn        # Vinny-side, version-pinned
    craydl_place_walls.dyn
  README.md                      # the round-trip + anchor setup, for Shay AND Vinny
```

Design rules (from Shay's endorsed process notes): *"documented pattern beats
'looks simpler'"*; *"two strikes = step back, not pivot sideways"*; verify the live
Blender 5.1 API rather than memory (the portfolio already logs 5.1 traps, e.g.
`GeometryNodeResampleCurve` mode is a menu **input socket**, and `NodeSocketMenu`
group-interface sockets are broken — use Int). The extractor registry keeps adding
element types to a one-function change.

---

## 9. Phased build plan (sequenced to execute when Shay frees up)

Sized in ADHD-friendly, one-goal-per-session blocks (matching how Shay already
phases the `/job-dossier`, `/source-assets`, `/ingest` skill work).

- **Phase 0 — Calibration & scaffold (½–1 session).**
  Open the live 61st blend; confirm how cans/walls are actually named, collected,
  and whether Revit IDs survived on any imported geometry. Establish the **ANCHOR**
  with Vinny. Build the addon scaffold (panel into "Craydl" tab, DRY_RUN/SCOPE,
  report plumbing). Run the **one-element round-trip calibration** (§3.3) and get
  Vinny's "it landed" before anything else. *Exit criterion: a single known point
  exported from Blender lands on its Revit twin.*

- **Phase 1 — Can-light positions for 61st (the v1 deliverable, 1–2 sessions).**
  Tagging operator + custom props + `DOCS_REVIEW`; `extract_can_light`; JSON+CSV
  writer; `craydl_place_cans.dyn`. Run on 61st's tagged cans. Include the
  **divergence flag** against the current RCP (the "RCP has zero cans" reality) so
  the export is reviewed, not blind. *Exit: Vinny places the 61st cans from the CSV
  with minimal rework.*

- **Phase 2 — Walls & soffits + reconciliation deltas (2–3 sessions).**
  `capture_baseline` / moved-vs-new classification; `extract_wall` / `extract_soffit`
  using the centerline/level/height/thickness model; reuse the interior/exterior
  classify method; `craydl_place_walls.dyn` (and evaluate the IFC-link alternative
  for geometry). Handle the **arch-vs-ID split** via `target_revit_file`.

- **Phase 3 — General tag-export workflow + (optional) trim/casing (later).**
  Generalize tagging into the reusable "promote to docs" flow across element types;
  asset-mark/preset conventions; only add casing/millwork if Vinny confirms the
  documentation value. Consider packaging as a clean addon (the portfolio's "addon =
  v2" standard) once the interface is stable.

Each phase ends with a Vinny check; nothing advances on Shay's say-so alone.

---

## 10. Decisions needed from humans BEFORE building

These cannot be guessed and block specific phases. Flagged explicitly.

**From Vinny (BIM lead) — blocks Phase 0/1:**
1. **The Revit import path** (§7). CSV+Dynamo (recommended), an existing
   family-placement macro (and its required column layout), or IFC link? This picks
   the export adapter.
2. **The anchor point & its coordinates** (§3). Which characteristic point
   (gridline/corner) is `ANCHOR`, and its Internal-Origin coordinate **in each of
   the two split files** (arch + ID).
3. **Per-element data needs** (§5). For cans: is XY + ceiling-Z + type + spacing +
   switching enough, or does he also need aiming/family-instance parameters? For
   walls: centerline + level + height + thickness + type-match — anything else
   (fire rating, function, structural usage)?
4. **Hosting expectation for cans:** data-for-him-to-host (recommended, given
   linked-ceiling fragility) vs auto-placed instances?

**From Adam / design (Paulina via JobTread) — blocks trustworthy 61st export:**
5. **Currency confirmation:** which RCP/model version is authoritative *right now*
   for 61st, given the "RCP has zero cans / Drive+Miro stale" situation? The export
   must be reconciled against the real current design, or it documents superseded
   intent.

**From Shay — design choices to lock (not blocking, but decide early):**
6. Confirm the **custom-property + `DOCS_REVIEW` collection** tagging (§4) over a
   pure-collection or naming scheme.
7. Confirm **JSON-canonical + CSV-adapter** output (§7) and meters-relative-to-anchor
   coordinates.

---

## 11. Risks & open unknowns (honestly flagged)

1. **Coordinate alignment (highest).** If the FBX/Max round-trip left a rotation or
   non-unit scale on imported geometry, the "pure translation" assumption (§3.2)
   breaks. *Mitigation: the Phase-0 round-trip calibration catches this before any
   real data ships.* Do not skip it.
2. **Revit-ID destruction by the cleanup pipeline (§2.2).** Without pre-cleanup ID
   capture, "moved existing element" reconciliation is impossible — you can only do
   "new." *Mitigation: add the baseline-snapshot step; or run reconcile on
   pre-cleanup collections via SCOPE.*
3. **Model split (arch vs ID).** Elements exported to the wrong Revit file are
   noise. *Mitigation: mandatory `target_revit_file` per element; shared anchor.*
4. **Design currency (61st specifically).** Documenting cans the current RCP dropped
   would actively mislead. *Mitigation: divergence flag + human confirm + decision
   #5.*
5. **Face-based fixture hosting to linked ceilings is fragile** (Autodesk-confirmed:
   wrong-face, upside-down, no vertical rotate). *Mitigation: ship positions-as-data
   for Vinny to host, not auto-hosted instances.*
6. **Blender 5.1 API drift.** This plan could not run Blender to verify 5.1
   specifics live. *Mitigation: verify against the running 5.1 at build time; the
   portfolio's logged 5.1 traps are the starting checklist.*
7. **I could not inspect the live 61st blend** (225 MB on Drive; not on this
   machine). The per-element data model is from documented structure, not observed
   objects. *Mitigation: Phase 0 opens the real file and corrects the model before
   coding extractors.*
8. **Scope creep into a general converter.** The temptation to "just handle
   everything" will bloat this into an unmaintainable Blender→Revit translator.
   *Mitigation: keep it the curated escape-hatch it is; extractor registry grows
   only when a real element type is promoted.*

---

### Appendix A — Source map (where each claim came from)

- **Existing addon shape, DRY_RUN/SCOPE/report, `clean_names` ID-strip, `join`
  destruct:** `craydl_revit_pipeline_addon.py` (Drive).
- **Ownership split, Revit→Blender FBX handoff, Max round-trip, FBX 0.01 scale,
  Imperial-inches/meters, `matrix_world` habit, Z=0 mount convention,
  Revit_Import/[category] collections:** `CRAYDL_REF_03_WORKING_CONTEXT.md`,
  `REF_04_PIPELINE.md`, `REF_04_PIPELINE_D5.md`, `craydl-blender-pipeline.md`.
- **61st: RCP has zero cans, arch-vs-ID split, JobTread currency, Connecter
  `Job:` tag, Bedrock builder:** `bedbrock-61st-job.md`, `craydl-job-workflow.md`.
- **LFG conventions (GN_LFG_*, modifier-params, JSON serialization, LFG_REF,
  asset_mark):** `lfg-project.md`.
- **Tool inventory, door-casing automation, profile-curve origins, "doors float
  6″", 5.1 API traps, process rules:** `blender-tools-portfolio.md`.
- **Shared coordinates / PBP / Survey / Internal Origin behavior; Dynamo CSV &
  meter-based placement; face-based lighting host fragility; wall properties /
  Wall.ByCurve:** Autodesk Revit help (multiple articles, en_US), retrieved
  2026-06-21.
- **Unreal/ArchVault conventions (typed prefixes, subprocess git-sync, self-
  contained, N-tab menu):** this repo (`Content/Python/*`, `README.md`).
