# bozzetto-zbrush-exporter

A ZBrush plugin that exports the **stages of a sculpt** — by walking the
**undo history** — as a sequential mesh (`.obj`) sequence for the
[Bozzetto](https://github.com/vidarrapp/bozzetto) timelapse viewer.

Instead of a pre-rendered video, Bozzetto stores each stage as *real 3D
geometry*, so you can relight, orbit, and step through a sculpt frame by
frame. This exporter produces the mesh sequence; Bozzetto's in-browser
`/create` editor builds the project + manifest from it.

> **Target:** ZBrush **2022 and upwards** (ZScript; no Python required).

---

## Status

**v0.1 — alpha, being validated on ZBrush 2022.** The core flow works:
**Detect Undo History** reports the correct step count, and **Export Undo
History** writes one OBJ per step into the chosen folder. A couple of items are
still marked `//VERIFY` in the source (mainly: that scrubbing the undo counter
yields correct *per-step* geometry — confirm by eyeballing the frames).
**Capture Stage** is a reliable manual fallback, independent of undo history.

---

## How it works

ZBrush keeps a scrubbable, **per-SubTool** undo history. The exporter reads how
many steps are stored, then steps from the oldest to the newest — exporting one
OBJ per (optionally sub-sampled) step. Each OBJ merges all *visible* SubTools
into a single mesh, named to sort sequentially (the prefix is whatever base
name you give in the Save dialog):

```
sculpt_0001.obj
sculpt_0002.obj
sculpt_0003.obj
...
```

---

## Repo layout

```
bozzetto-zbrush-exporter/
├─ README.md
├─ LICENSE
├─ docs/
│  └─ DESIGN.md                 design notes & rationale
├─ src/
│  ├─ bozzetto_exporter.txt     the exporter plugin (ZScript source)
│  └─ bozzetto_decimate_dm.txt  optional in-ZBrush batch decimation
├─ scripts/
│  └─ decimate_sequence.py      optional PyMeshLab batch decimation (CLI)
├─ build/                       compiled .zsc goes here (optional)
└─ examples/
   └─ sample-sequence/          sample frames (placeholder)
```

---

## Install

1. **Load it:** in ZBrush open the **ZScript** palette → **Load**, and choose
   `src/bozzetto_exporter.txt`. Loading *is* the compile — ZBrush runs the
   script (a **Bozzetto Exporter** subpalette appears under **ZPlugin**) and
   writes a `bozzetto_exporter.zsc` next to the `.txt`.
2. **Auto-load on startup (optional):** copy that `.zsc` into
   `Pixologic/ZBrush 2022/ZStartup/ZPlugs64/`.
3. **While iterating:** ZBrush may reload the cached `.zsc` instead of an edited
   `.txt`. Delete the `.zsc` (or restart ZBrush) before re-loading the `.txt`.

---

## Usage

### 1. Prepare ZBrush (one-time, for best results)
- **Preferences ▸ Undo History ▸ Max Undo History** — raise this; it caps how
  many stages you can capture.
- Enable **save undo history** so history survives where possible.
- The undo history is **per-SubTool**. v0.1 targets the **active SubTool**;
  single-SubTool sculpts are the clean case.

### 2. Export an undo-history sequence
1. Select the SubTool you sculpted.
2. **Set Output Folder** — in the Save dialog, browse to your folder and set a
   **base name**, then **Save** (no file is created). The folder *and* the name
   are used: the name becomes the frame prefix (`dragon_` → `dragon_0001.obj`).
3. **Detect Undo History** — confirms the plugin can read your undo counter and
   reports the number of stored steps. *Do this first.*
4. *(Optional)* set:
   - **Export Subdiv Level** — `0` keeps the current level; lower = smaller files.
   - **Every Nth Step** — subsample (e.g. `5` = every 5th step).
   - **Max Frames (0=all)** — cap the count; the stride is auto-derived.
   - **Filename Padding** — digits in the frame number (`4` → `0001`).
5. **Export Undo History** — starts a fresh sequence at frame 1 (asks before
   overwriting existing frames) and writes the sequence.

### 3. Or capture stages manually
- **Capture Stage** exports the current state as the next frame. Use it as you
  sculpt, or as a fallback if undo stepping is constrained.
- **New Sequence (Reset)** sets the frame counter back to `1`.

### Export settings & normals
Before each export the plugin automatically sets **Tri** on and **Qud / Txr /
Mrg** off (triangulated, no UVs) — so **no `.mtl` files are written**.
Normal-direction options are left as you set them in
**Preferences ▸ ImportExport ▸ Export**: if frames look inside-out in Bozzetto,
toggle **eFlipNormals**, and check that **eFlipMapVert** / **eSwitchYZ** are off.

---

## Decimation (separate, optional)

Bozzetto wants roughly **a few thousand to a few hundred thousand triangles per
frame**. You often hit that just by choosing a lower **Export Subdiv Level** —
no decimation needed. When you *do* need it, keep it as its own step. Two
interchangeable options:

### Option A — Command line (PyMeshLab) · most robust
```bash
pip install pymeshlab
python scripts/decimate_sequence.py ./raw ./decimated --faces 50000
# or by ratio:
python scripts/decimate_sequence.py ./raw ./decimated --percentage 0.05
```
Processes the whole folder in one command. See `--help` for all options.

### Option B — In-ZBrush (Decimation Master) · artist-friendly
`src/bozzetto_decimate_dm.txt` batch-decimates the sequence inside ZBrush.
Edit its CONFIG block (folders, prefix, frame range, target K-polys), load it,
and press **Bozzetto Decimate**. It **reuses Marcus Civis's `Batch_DM` plugin
if installed** (the proven path) and falls back to stock Decimation Master
otherwise. Because Decimation Master ends script flow, it uses a memblock
"replay" loop — see the header comment. This script needs the most
on-hardware tuning; the PyMeshLab route is the safe default.

---

## Orientation & units

ZBrush OBJ export is Y-up-compatible with most pipelines, which matches
Bozzetto (Three.js / glTF, Y-up). So in Bozzetto's editor the **"Z-up
conversion" toggle should stay OFF** — but **verify on a real model** and
flip if your sculpt comes in rotated.

## Into Bozzetto

Point Bozzetto's **`/create`** editor at your (optionally decimated) folder;
it builds the project + manifest from the sorted mesh sequence.

---

## Status of commands

### Confirmed (ZBrush 2022 + the Command Reference)
- Undo-history detection reports the correct step count; the exporter writes the
  sequence into the chosen folder.
- `MemReadString` writes into a target variable
  (`[MemReadString, block, var, offset]`).
- Paths converted to **forward slashes** on input (`slashify`,
  `StrExtract`/`StrToAsc`); `StrMerge` numeric→string padding works.
- `FileNameExtract` flag **`1`** = folder, **`2`** = name (used as the prefix).
- `FileNameAsk` is a **Save** dialog when given a default name.
- `ISlider`, `Note`, `FileNameSetNext`, `FileExists`, `MessageOKCancel` confirmed.

### Still to verify (`//VERIFY`)
- That **setting the undo counter scrubs the geometry** to each step (eyeball the
  frames) and is synchronous in a loop.
- `Tool:Geometry:SDiv` (setting the export subdivision level).
- The ImportExport export-toggle paths (auto-set `Txr/Mrg/Qud/Tri`) — probed via
  `IExists`, so harmless if a name differs; tell me if `.mtl` files persist.
- Stock **Decimation Master** control names in the fallback path.

### Known behaviour
- **`.mtl` files** are avoided by auto-disabling **Txr** (UV export). If any slip
  through, delete with `del *.mtl` (Windows) / `rm *.mtl` (macOS/Linux).
- **Re-exporting** the full timeline restarts at frame 1 and asks before
  overwriting existing frames. **Capture Stage** keeps incrementing.

---

## Credits

- The memblock **"replay" pattern** for driving Decimation Master from ZScript
  is courtesy of **Marcus Civis** (`Batch_DM` on ZBrushCentral).
- [Bozzetto](https://github.com/vidarrapp/bozzetto) by vidarrapp.

## License

MIT — see [LICENSE](LICENSE).
