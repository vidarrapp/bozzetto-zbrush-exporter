# bozzetto-zbrush-exporter — Design

A ZBrush plugin that exports the stages of a sculpt — primarily by walking the
**undo history** — as a sequence of mesh files for the
[Bozzetto](https://github.com/vidarrapp/bozzetto) timelapse viewer.

Target: **ZBrush 2022 and upwards.**

---

## 1. Context

**Bozzetto** (the consumer) is a web viewer/editor that stores each stage of a
sculpt as *real 3D geometry* rather than pre-rendered video, enabling
interactive relighting, orbiting, and frame-by-frame stepping. Relevant facts:

- Ingests `.obj` or `.glb` files, **one mesh per stage**, named to sort
  sequentially (e.g. `sculpt_001.obj`, `sculpt_002.obj`, …).
- Recommended density: **a few thousand to a few hundred thousand triangles per
  frame**.
- Three.js / glTF based → **Y-up**. Its "Z-up conversion" toggle exists for
  Blender/other DCC files.
- Has an in-browser editor (`/create`) that builds the project + manifest from
  an uploaded/converted mesh sequence. **We rely on this** — the exporter
  produces only the mesh sequence (see §2).

**ZBrush 2022+** (the producer) imposes constraints that drive the design:

1. **No native geometry timelapse**, but it *does* keep a scrubbable **undo
   history** we can exploit (see §4).
2. **ZScript is synchronous/blocking** on 2022. Fine for our batch-style export;
   rules out a background auto-timer. (Python only arrives in 2025+ builds.)
3. **Sculpts are millions of polys; Bozzetto wants ≤ a few hundred K.** Density
   is handled by export subdivision level **plus downstream decimation** in
   MeshLab or similar (see §6). Native **OBJ export** is reliable and merges all
   visible SubTools; **GLB is not native** → OBJ is the target.

---

## 2. Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Name** | `bozzetto-zbrush-exporter` | Explicit and discoverable; says exactly what it does. |
| **Capture trigger** | **Undo-history export (primary)** + manual snapshot (secondary/fallback) | Artist sculpts using history, so the history *is* the timeline. Manual snapshot remains as a safety net if history stepping is constrained. |
| **Output** | Mesh sequence only (no manifest) | Bozzetto's editor builds the manifest; keeps us decoupled from its evolving `manifest.ts`. |
| **Density / tiers** | Single **SD** tier: export subdivision level **+ external decimation** | Subdiv level controls raw size; final triangle budget is hit downstream in MeshLab/Decimation Master. |

### Non-goals (v1)
- No `manifest.json` generation.
- No HD tier.
- No GLB output.
- No timed auto-capture.
- No *in-ZBrush* guarantee of the final triangle budget (decimation is a
  downstream step).

---

## 3. Goal

After a history-based sculpt session, the artist runs the exporter and gets
`sculpt_0001.obj … sculpt_NNNN.obj` — one OBJ per (sub-sampled) undo step —
optionally decimates them in MeshLab, then points Bozzetto's editor at the
folder.

---

## 4. Capture model

### 4.1 Undo-history export (primary)
ZBrush's Edit palette exposes an **Undo Counter slider** that navigates the
**active SubTool's** undo history (an alternative to the Undo/Redo buttons).
Because a slider is settable by index from ZScript, the intended mechanism is:

1. Read the Undo Counter's **max** (= number of stored history steps).
2. Loop from the oldest step to the newest; for each selected step:
   set the Undo Counter to that index → export the current mesh as the next
   frame.
3. Restore the counter to the latest step when done.

**Modes (settings):**
- **Export all** — one frame per history step.
- **Every Nth step** — subsample (e.g. every 5th) to keep frame counts sane.
- Optional **max-frames cap** (auto-derive the stride from total steps).

**Important behaviours / caveats (confirm in the spike, §7):**
- Undo history is **per-SubTool**, not a global timeline. Single-SubTool sculpts
  are the clean case; multi-SubTool needs a decision (export active SubTool only
  vs. iterate SubTools).
- History is **capped** by *Preferences ▸ Undo History ▸ Max Undo History* and
  can be lost on some operations. The exporter should read the available count
  rather than assume; docs will tell artists to **raise Max Undo History** and
  **enable "save undo history"** for best results.
- Setting the counter inherits the *current* subdivision level / SubTool
  visibility at export time.
- Exact ZScript command path for the Undo Counter slider (`ISet`/`IGet`) is
  **TBD** against the ZScript Command Reference (2022) and must be verified.

### 4.2 Manual snapshot (secondary / fallback)
A **Capture Stage** button (hotkey-bindable) exports the current state as the
next frame on demand. Always reliable, independent of history limits — the
safety net if undo-history stepping proves constrained for a given workflow.

---

## 5. Export pipeline (per exported frame)

1. Ensure a Tool/SubTool is active and an output folder is set.
2. (Undo mode) set the Undo Counter to the target step.
3. (Optional) set the active subdivision level — approximately
   `[ISet, Tool:Geometry:SDiv, level]`. ZBrush exports the active level.
4. Build filename `<dir>/<prefix><index zero-padded>.obj`
   (default prefix `sculpt_`, 4-digit pad → `sculpt_0001.obj`).
5. `[FileNameSetNext, "<path>"]` then `[IPress, Tool:Export]`.
   *(Command names to confirm against the ZScript Command Reference 2022.)*
6. OBJ export merges all visible SubTools into one file — no manual merge.

---

## 6. Density & the downstream pipeline

The exporter does **not** try to guarantee Bozzetto's triangle budget in ZBrush.
Instead:

- Export at a chosen **subdivision level** (keeps raw size reasonable).
- **Decimate downstream** to hit a few-K–few-hundred-K target. Two paths:
  - **MeshLab / PyMeshLab** batch decimation over the OBJ sequence (artist's
    stated preference). *Plan to ship a sample `pymeshlab` / `meshlabserver`
    batch script in `examples/` so the whole sequence decimates in one command.*
  - **Decimation Master** inside ZBrush *if/when* it proves scriptable
    (historically fragile from ZScript — future work).
- Then load into Bozzetto's `/create` editor.

**Orientation / units:** ZBrush OBJ export is Y-up-compatible in most pipelines,
matching Bozzetto, so the Bozzetto **Z-up toggle should stay OFF** — *verify on a
real model*; the exporter can pre-rotate if needed.

---

## 7. Milestone 0 — feasibility spike (critical path)

Because the whole capture flow now rests on undo-history stepping, **prove it
first** with a throwaway script before building the real plugin:

- Detect the number of undo-history steps for the active SubTool.
- Step deterministically via the **Undo Counter slider** (preferred) or
  Undo/Redo presses (fallback).
- Export a correct OBJ at each step on a non-trivial single-SubTool sculpt.
- Note behaviour across subdivision changes and the Max-Undo cap.

**Exit criteria:** a clean, correctly-ordered OBJ sequence from a real session.
If the slider approach fails, fall back to manual snapshot as the v1 primary and
revisit history export later.

---

## 8. Plugin UX & architecture

**UI — a "Bozzetto" subpalette** (ZScript-created):
- **Set Output Folder** — choose/persist the project directory.
- **Export Undo History** — primary action; mode = all / every-Nth + stride.
- **Capture Stage** — manual single-frame export (hotkey-bindable).
- **New Sequence / Reset** — reset the frame index.
- **Subdivision level** + **prefix/padding** settings.
- Frame counter / last tri-count readout.

**Tech:**
- **Language:** ZScript (`.txt` → compiled `.zsc`), runs on 2022 → current.
  Optional Python variant for 2025+ is future work.
- **Install:** drop into `ZStartup/Macros` (auto-loads) or load via
  *Preferences ▸ ZPlugin/ZScript*.
- **State:** frame index + output path in ZScript variables; persist settings
  via ZBrush's variable store if practical.
- **No external runtime dependencies** (MeshLab is a separate, optional step).

---

## 9. Roadmap

- **M0 — Undo-history spike** (§7). Gate before everything else.
- **v0.1 — Undo-history exporter.** Subpalette, Set Output Folder, Export Undo
  History (all / every-Nth), subdiv level, sequential OBJ output, frame counter.
  Verified end-to-end into Bozzetto.
- **v0.2 — Manual snapshot** + MeshLab/PyMeshLab sample decimation script.
- **v0.3 — Polish.** Configurable prefix/padding, orientation bake, persisted
  settings, multi-SubTool handling, install/usage docs.
- **Future.** HD tier (sd+hd), scripted Decimation Master, optional
  `manifest.json` generation, Python timed capture (2025+).

---

## 10. Open questions / risks

1. **Undo Counter slider** — exact ZScript command path + that it yields correct
   per-step geometry. (M0 spike.)
2. **Per-SubTool history** — single-SubTool assumption vs. multi-SubTool policy.
3. **History caps / persistence** — document Max Undo + "save undo history".
4. **Exact ZScript commands** for export and subdivision set — confirm vs. the
   2022 Command Reference.
5. **Orientation** — verify ZBrush→Bozzetto axis on a real model.
6. **Filename convention** — confirm prefix/padding (default `sculpt_0001.obj`).

---

## 11. Repo layout (proposed)

```
bozzetto-zbrush-exporter/
├─ README.md
├─ LICENSE
├─ docs/
│  └─ DESIGN.md              (this document)
├─ src/
│  └─ bozzetto_exporter.txt   (ZScript source)
├─ build/
│  └─ BozzettoExporter.zsc    (compiled, optional)
├─ scripts/
│  └─ decimate_sequence.py   (PyMeshLab batch decimation helper)
└─ examples/
   └─ sample-sequence/       (a few sculpt_000N.obj + screenshots)
```

---

## References
- Bozzetto README — https://github.com/vidarrapp/bozzetto/blob/main/README.md
- ZScripting guide — https://help.maxon.net/zbr/en-us/Content/html/user-guide/customizing-zbrush/zscripting/zscripting.html
- ZScript Command Reference (2022) — https://help.maxon.net/zbr/en-us/Content/Resources/Uploads/ZScript-Command-Reference-2022.pdf
- Undo History — https://help.maxon.net/zbr/en-us/Content/html/user-guide/3d-modeling/undo-history/undo-history.html
- Preferences ▸ Undo History (Max Undo, save history) — https://help.maxon.net/zbr/en-us/Content/html/reference-guide/preferences/undo-history/undo-history.html
- Undo History Movies (native video timelapse) — https://docs.pixologic.com/user-guide/movies/undo-history-movies/
- "Export history as OBJ sequence" (community request) — https://www.zbrushcentral.com/t/export-history-as-obj-sequence/317652
- Decimation Master — https://help.maxon.net/zbr/en-us/Content/html/user-guide/zbrush-plugins/decimation-master/decimation-master.html
