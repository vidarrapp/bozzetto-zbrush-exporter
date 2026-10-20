# bozzetto-zbrush-exporter — Design

A ZBrush plugin that exports the stages of a sculpt — primarily by walking the
**undo history** — as a sequence of mesh files for the
[Bozzetto](https://github.com/vidarrapp/bozzetto) timelapse viewer.

Target: **ZBrush 2022 and upwards.**

*Last refreshed 2026-10-20, after v0.1 was validated end to end and against the
current Bozzetto README.*

---

## 1. Context

**Bozzetto** (the consumer) stores each stage of a sculpt as *real 3D geometry*
rather than pre-rendered video, so a timelapse can be relit, orbited and stepped
frame by frame. It is now two products:

- **Bozzetto Web** — the web app: gallery, viewer, Sculpt and Armature modes,
  accounts, Community, and the two editors that ingest a mesh sequence.
- **Bozzetto Studio** — a separate desktop product. Recording a timelapse while
  sculpting moved there from Web, and Studio *exports the same frame format*.

This exporter is the **ZBrush path into that frame format**: what Studio records
for its own sculpting, this produces from a ZBrush undo history.

Facts the design depends on:

- **Ingest:** a sequence of `.obj` or `.glb` files, **one mesh per stage**, named
  to sort in order (e.g. `sculpt_0001.obj`, `sculpt_0002.obj`, …). Two editors
  take it:
  - **`/create`** (gallery → **Create → Create timelapse**) — runs in the
    browser. A guest gets a self-contained `.html`; signed in, **Save to My
    projects** uploads the frames as a project.
  - **`/admin`** (the editor) — create a project, drop in the sequence; OBJ is
    converted to glTF-binary in a Web Worker while it uploads.
  Bozzetto builds the project and manifest itself; the exporter produces only
  the mesh sequence (§2).
- **Orientation:** three.js / glTF, **Y-up** by default. `/create` has an
  **OBJ files are Z-up** checkbox for Blender-style exports. The exporter writes
  either (§6).
- **Units and scale:** Bozzetto works in **metres** (1 unit = 1 m, shown in cm),
  on a fixed floor at 0. An OBJ carries no units, so a sequence arrives at the
  file's own coordinates and is scaled once in Bozzetto (§6.1).
- **Density:** a few thousand to a few hundred thousand triangles a frame plays
  well. (Sculpt mode itself goes to 16M triangles, but every timelapse frame is
  downloaded and held, so the budget still applies.)
- **`.bozz`** is Bozzetto's own Sculpt scene container. It is not a target.

**ZBrush 2022+** (the producer) imposes constraints that drive the design:

1. **No native geometry timelapse**, but it *does* keep a scrubbable **undo
   history** we can exploit (§4).
2. **ZScript is synchronous/blocking** on 2022. Fine for a batch-style export;
   rules out a background auto-timer. (Python only arrives in 2025+ builds.)
3. **Sculpts are millions of polys; Bozzetto wants ≤ a few hundred K.** Density
   is handled by export subdivision level **plus optional decimation** (§6).
   Native **OBJ export** is reliable and merges all visible SubTools. ZBrush has
   **no native GLB export**, so OBJ stays the target even though Bozzetto now
   accepts GLB directly.
4. **ZBrush has no units.** Exported coordinates are the tool's own, arbitrary
   size (§6.1).

---

## 2. Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Name** | `bozzetto-zbrush-exporter` | Explicit and discoverable; says exactly what it does. |
| **Capture trigger** | **Undo-history export (primary)** + manual snapshot (fallback) | The artist sculpts with history, so the history *is* the timeline. Manual snapshot stays as a safety net. |
| **Output** | Mesh sequence only (no manifest) | Bozzetto's editors build the manifest; keeps us decoupled from its evolving format. |
| **Format** | Triangulated OBJ, no UVs | Native and reliable in ZBrush; no `.mtl` clutter; Bozzetto converts OBJ to glTF itself. |
| **Density** | Export subdivision level **+ separate, optional decimation** | Subdiv level controls raw size; decimation is its own step because it is often unnecessary. |
| **Scale** | Set once in Bozzetto, not baked in by the exporter | ZBrush has no units; one Set scale in Bozzetto covers every frame. |

### Non-goals (v1)
- No `manifest.json` generation.
- No HD tier.
- No GLB output.
- No timed auto-capture.
- No in-ZBrush guarantee of the final triangle budget.

---

## 3. Goal

After a history-based sculpt session, the artist runs the exporter and gets
`<prefix>0001.obj … <prefix>NNNN.obj` — one OBJ per (sub-sampled) undo step —
optionally decimates them, then drops the folder into Bozzetto's `/create` or
`/admin` and sets the scale once. **Achieved in v0.1** (validated on ZBrush 2022:
correct step count, correct per-step geometry, correct orientation and workable
density in Bozzetto).

---

## 4. Capture model

### 4.1 Undo-history export (primary)
ZBrush's **Edit ▸ Tool** sub-palette has an **Undo Counter** slider that navigates
the **active SubTool's** undo history. The exporter:

1. Probes for the Undo Counter's interface path (**Detect Undo History**) and
   reads its max (= number of stored steps).
2. Loops from the oldest step to the newest; for each selected step it sets the
   counter to that index and exports the current mesh as the next frame.
3. Restores the counter to where it was.

Setting the counter scrubs the geometry synchronously, so a plain loop works; no
"replay" pattern is needed (unlike Decimation Master, §6).

**Modes:**
- **Export all** — one frame per history step.
- **Every Nth step** — subsample to keep frame counts sane.
- **Max frames** cap — the stride is derived from the step count.

A full-history export always starts a fresh sequence at frame 1 and asks before
overwriting existing frames.

**Caveats:**
- Undo history is **per-SubTool**, not a global timeline. Single-SubTool sculpts
  are the clean case; multi-SubTool handling is open (§10).
- History is **capped** by *Preferences ▸ Undo History ▸ Max Undo History* and can
  be lost on some operations. The exporter reads the available count rather than
  assuming one; artists should raise Max Undo History and enable save undo
  history.
- Each step exports at the *current* subdivision level and SubTool visibility.

### 4.2 Manual snapshot (fallback)
**Capture Stage** exports the current state as the next frame on demand,
independent of history limits. **New Sequence (Reset)** returns the counter to 1.

---

## 5. Export pipeline (per frame)

1. An output folder and base name are set (**Set Output Folder**: a Save dialog,
   so the folder need not contain a file; the name becomes the frame prefix).
2. The export options are set (§6): triangulated, no UVs, chosen up-axis.
3. (Undo mode) the Undo Counter is set to the target step.
4. (Optional) the subdivision level is set via `Tool:Geometry:SDiv`.
5. The filename is built as `<folder>/<prefix><zero-padded index>.obj`, with
   forward slashes (ZScript's `StrMerge` drops backslashes).
6. `[FileNameSetNext, path]` then `[IPress, Tool:Export]`. OBJ export merges all
   visible SubTools into one file.

State that must survive between button presses (frame index, folder, prefix,
undo path) lives in **memblocks**, since ZScript variables can be flushed when
another script loads.

---

## 6. Density, export settings & the downstream pipeline

**Export settings** are applied automatically before each export, under
*Preferences ▸ ImportExport ▸ Export*:
- **Tri** on, **Qud** off — triangulated, as three.js renders.
- **Txr** off and **Mrg** off — no UVs, so ZBrush writes **no `.mtl`** files
  (Bozzetto never uses UVs).
- **Orientation** from the **Export Z-up** control: `eSwitchYZ` off = **Y-up**
  (Bozzetto's default, confirmed correct); on = **Z-up**, imported with
  Bozzetto's **OBJ files are Z-up** checkbox. The other axis and normal flips are
  forced off, so the result never depends on leftover manual settings.

**Density** is not guaranteed inside ZBrush:
- Export at a chosen **subdivision level** — often enough on its own.
- When it is not, **decimate as a separate step**, either:
  - **command line**: `scripts/decimate_sequence.py` (PyMeshLab, quadric edge
    collapse to a face count or ratio, over the whole folder); or
  - **in ZBrush**: `src/bozzetto_decimate_dm.txt` drives Decimation Master over
    the sequence. Pressing a Decimation Master button ends ZScript execution, so
    it uses a memblock **replay** loop, and it prefers Marcus Civis's proven
    `Batch_DM` wrapper when installed.
- Then drop the folder into `/create` or `/admin`.

### 6.1 Scale

ZBrush has no units, so the frames carry the tool's own arbitrary size, and
Bozzetto (in metres) cannot know how big the sculpt really is. It does not guess:
a sequence arrives at the file's coordinates, and **Set scale** in the `/admin`
editor fixes it once:

- Type the model's **real height in centimetres**, measured on the frame showing.
- **One factor** scales **every frame**, and the model is stood on the floor at 0.
- It is saved with the look (`presentation.scale` and `presentation.lift`, plus
  `units: 'm'`), so the viewer and the `.html` export play it at that size.
- **Not now** leaves it unscaled for the session.

What this asks of the exporter:
- **All frames must share one coordinate frame.** They do, because every frame
  is the same tool exported in place. Moving or rescaling the *whole* tool
  partway through the history makes the model jump in the timelapse. Bozzetto
  applies one factor, so it cannot hide that.
- **Measure on the last frame.** Set scale reads the frame on screen, and the
  finished sculpt is the one whose height the artist knows.
- **No scale baked in.** Bozzetto's one-step Set scale is simpler and more exact
  than guessing a ZBrush-to-metres factor. An optional export scale that writes
  frames at real size is listed as future work (§9).

---

## 7. Milestone 0 — feasibility spike (done)

The capture flow rested on undo-history stepping, so it was proven first.
**Result:** passed on ZBrush 2022. Detect Undo History found the counter and
reported the right step count (19 on the test model), and stepping it produced a
correctly ordered OBJ sequence that progresses through the sculpt.

---

## 8. Plugin UX & architecture

**UI — the "Bozzetto Exporter" subpalette** under **ZPlugin**:
- **Set Output Folder** — Save dialog: folder + base name (the name is the prefix).
- **Export Subdiv Level**, **Export Z-up**, **Filename Padding**, **Every Nth
  Step**, **Max Frames**, **Next Frame #**.
- **Detect Undo History** — probes the Undo Counter and reports the step count.
- **Export Undo History** — the primary action.
- **Capture Stage** — manual single-frame export.
- **New Sequence (Reset)**.

**Tech:**
- **Language:** ZScript. Loading `src/bozzetto_exporter.txt` from the ZScript
  palette compiles it and writes a `.zsc` beside it. No compiled binary is kept
  in the repo; it would go stale with every source change.
- **Install:** load the `.txt` each session, or copy the generated `.zsc` into
  `ZStartup/ZPlugs64/` to auto-load.
- **State:** memblocks (§5).
- **No external runtime dependencies.** PyMeshLab is only needed for the
  optional command-line decimation.

---

## 9. Roadmap

- **M0 — Undo-history spike.** Done (§7).
- **v0.1 — Undo-history exporter.** Done and validated end to end into
  Bozzetto: export undo history (all / every-Nth / max frames), Capture Stage,
  output folder + prefix from the Save dialog, overwrite guard, triangulated
  no-`.mtl` output, Y-up/Z-up, plus both decimation paths.
- **Next — polish.**
  - Verify the **Z-up** winding on hardware.
  - Verify the **Export Subdiv Level** control (`Tool:Geometry:SDiv`).
  - Hardware-test the two decimation paths.
  - **Multi-SubTool** handling.
  - Persist settings across ZBrush restarts.
- **Future.** HD tier; an optional **export scale** so frames arrive at real size
  without Set scale; optional `manifest.json`; Python timed capture (2025+).

---

## 10. Open questions / risks

1. **Undo Counter** — RESOLVED: probed at runtime; scrubbing yields correct
   per-step geometry.
2. **Per-SubTool history** — open: single-SubTool today; multi-SubTool policy to
   decide.
3. **History caps / persistence** — documented (raise Max Undo History, enable
   save undo history).
4. **Exact ZScript commands** — RESOLVED against the 2022 Command Reference and
   live testing, except `Tool:Geometry:SDiv` (still to verify).
5. **Orientation** — RESOLVED: Y-up confirmed; Z-up offered via `eSwitchYZ`
   (winding still to verify).
6. **Filename convention** — RESOLVED: the prefix is the Save-dialog name,
   zero-padded to 4 digits by default (`sculpt_0001.obj`).
7. **Scale** — RESOLVED by design: set once in Bozzetto (§6.1). A sequence must
   not move or rescale the whole tool partway through.

---

## 11. Repo layout

```
bozzetto-zbrush-exporter/
├─ README.md
├─ LICENSE
├─ docs/
│  └─ DESIGN.md                 (this document)
├─ src/
│  ├─ bozzetto_exporter.txt     (the exporter plugin, ZScript)
│  └─ bozzetto_decimate_dm.txt  (optional in-ZBrush batch decimation)
├─ scripts/
│  └─ decimate_sequence.py      (optional PyMeshLab batch decimation)
├─ build/                       (local build output; .zsc is git-ignored)
└─ examples/
   └─ sample-sequence/          (placeholder)
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
