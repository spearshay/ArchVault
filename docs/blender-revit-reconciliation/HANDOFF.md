# Local-session kickoff — Blender→Revit reconciliation, deeper pass

**Why this exists:** the first planning pass ran in a *remote cloud* session anchored
to the Unreal `ArchVault` repo. That session could reach Google Drive, Miro index,
and Autodesk Revit docs — but **not** the `E:\` drive, the live `.blend` files, or
the Blender connecter MCP. Shay chose to take the next, deeper pass **locally**,
where those *are* reachable. This file tells the local session exactly where to pick
up so it doesn't re-discover what's already settled.

**Read `PLAN.md` (same folder) first.** It is the substantive architecture and is
correct as far as it goes; this handoff only lists what the local pass must *verify
against real state* and what to correct.

---

## What was already established remotely (don't re-derive — confirm)

- Existing addon `craydl_revit_pipeline_addon.py` is the template: thin N-panel under
  the **`"Craydl"`** tab over source-of-truth scripts, injecting `DRY_RUN` / `SCOPE`
  / `RUN_STAGES`, capturing stdout as a report. New toolkit slots into the same tab.
- **Hazard:** the cleanup pipeline's `clean_names` **strips Revit IDs** and `join`
  collapses element identity. "Moved existing element" reconciliation must capture
  the Revit ID *before* cleanup runs.
- **61st reality:** current approved RCP has **zero can lights**; Vinny split the
  model **arch vs ID**; Drive/Miro copies often stale vs JobTread. Export must carry
  `target_revit_file` and a divergence flag, timestamped against a named RCP version.
- **Coordinates:** Blender internal = meters, Z-up; Revit Z-up too (no axis swap);
  Dynamo places in meters. Strategy = export **meters relative to a shared ANCHOR**
  keyed to Revit **Internal Origin** (PBP/Survey drift). Gated by a one-element
  round-trip calibration.
- **Tagging:** custom property authoritative (`craydl_docs_*`), `DOCS_REVIEW`
  collection for UI. Not naming (cleanup renames).
- **Import path (recommended):** CSV ⇄ Dynamo (`Data.ImportCSV` →
  `FamilyInstance.ByPoint` / `Wall.ByCurve`), JSON canonical + CSV adapter. Ship the
  Dynamo graphs as part of the toolkit. IFC-link is the phase-2 wall alternative.
- **LFG** is a sellable pendant generator, **not** the can-light mechanism — mirror
  its conventions (`GN_LFG_*`, modifier-params, JSON serialization, `LFG_REF`
  dropzone), don't treat it as the data source.

---

## Gap A — read the LIVE scripts (authoritative `E:\` versions, not Drive copies)

Location from the addon's `DEFAULT_SCRIPTS_DIR`:
`E:\My Drive\Blender\Plugins and Scripts\Shay's Scripts\`

1. **`revit_fbx_cleanup.py`** — confirm the real `RUN_STAGES` keys, the `run_pipeline`
   entry, and **exactly where/how `clean_names` mutates object names** and whether any
   original Revit identifier (UniqueId / ElementId) is preserved anywhere before it
   runs. This determines whether "moved" reconciliation needs a new baseline-capture
   step or can piggyback on existing data.
2. **`fixture_swap.py`** — read `SWAP_MAP` and the **transform-placed vs baked-mesh**
   detection (`is_baked_mesh`). Transform-placed fixtures (downlights) carry loc/rot
   on the object — that is the can-light position source; baked-mesh ones don't.
   Confirm which category the 61st cans fall into.
3. **`REF_06_BLENDER_PYTHON_PATTERNS.md` / `REF_06b_BLENDER_PYTHON_REASONING.md`** —
   the addon/operator/panel/`AddonPreferences`/poll patterns to match (REF_06b has an
   LFG-specific note on AddonPreferences lookup tables + per-object params).
4. **`blender-wall-interior-exterior-classify.md`** + its script — the ray method for
   splitting/classifying walls; reuse for the phase-2 wall extractor.
5. **`tag_connecter.py`** — Shay's existing custom-property/tag write pattern (the
   `Connecter Job:<NAME>` convention). Match its idioms for the `craydl_docs_*` tags.

---

## Gap B — inspect the LIVE 61st blend (this is the part only local can do)

File: `SIXTY-FIRST_(BEDROCK)_WIP A.blend` (E:\ working copy; ~225 MB).
**Use the Blender connecter MCP to read scene data — never trust screenshots.**

Build-step-zero checklist (correct `PLAN.md §5` against what's actually there):

1. **Enumerate the promoted elements.** How are the can lights / moved walls /
   soffits / millwork actually **named** and **collected**? (Expected: under
   `Revit_Import/[category]` or hand-sorted collections.) Record real names.
2. **Can lights:** are they transform-placed objects (loc/rot on object, mesh at
   origin) or instances? Read 3–5 real `matrix_world` translations. Is there a
   ceiling/host object to derive `ceiling_ref` Z from? Any existing custom props?
3. **Walls/soffits:** is centerline derivable from the mesh, or are they joined
   blobs (cleanup `join` already run)? If joined, identity is gone — note it.
4. **Coordinate sanity (critical, validates `PLAN.md §3.2`):** pick one element that
   exists in *both* Vinny's Revit and this blend; confirm the FBX/Max import left
   **no rotation and unit scale = 1** on it (else the "pure translation" anchor math
   breaks). Identify the **ANCHOR** candidate (a gridline corner present in both).
5. **Custom-property survival:** verify writing a `craydl_docs_state` prop on an
   object persists through save/reload and isn't touched by the cleanup scripts.

Then run the **one-element round-trip calibration** with Vinny before building any
extractor (PLAN.md §3.3).

---

## How to launch the local session so it has the right scope

- Run Claude Code on the **Windows machine** with `E:\` mounted and the **Blender
  connecter MCP** configured/live (plus Google Drive, Autodesk Help, Miro if you want
  them). Point/clone this branch so `PLAN.md` + this file are available, **or** keep
  the docs handy and run the session in the scripts/project working folder.
- First instruction to that session: *"Read
  `docs/blender-revit-reconciliation/PLAN.md` and `HANDOFF.md`, then work Gap A and
  Gap B; correct the plan against real state; do not write production code yet."*

---

## Carried-forward human decisions (still blocking — PLAN.md §10)

- **Vinny:** import path (CSV+Dynamo?), the ANCHOR point + its Internal-Origin
  coords in **each** split file, per-element data needs, host-vs-data for cans.
- **Adam/Paulina:** which RCP/model version is authoritative for 61st *right now*.

---

## Also still open from the remote pass (optional, nice-to-have)

- **Miro `Job Flow` board** was never read verbatim (the research subagent stalled on
  it). If a local or remote session can read it, fold the exact pipeline-stage labels
  into PLAN.md §1 so the reconciliation step is sited precisely in the documented flow.
