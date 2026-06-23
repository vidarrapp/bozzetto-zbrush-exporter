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

**v0.1 — alpha.** The export logic follows the ZScript Command Reference and a
verified community plugin, but it was authored without a running ZBrush, so a
few command paths are marked `//VERIFY` in the source and need a first pass on
real hardware. **The single most important thing to confirm is undo-history
stepping** — the **Detect Undo History** button does this for you (see below).
If that proves constrained on your setup, **Capture Stage** (manual snapshot)
is a reliable fallback that does not depend on the undo history at all.

---

## How it works

ZBrush keeps a scrubbable, **per-SubTool** undo history. The exporter reads how
many steps are stored, then steps from the oldest to the newest — exporting one
OBJ per (optionally sub-sampled) step. Each OBJ merges all *visible* SubTools
into a single mesh, named to sort sequentially:

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

## Install (exporter)

1. **Compile** `src/bozzetto_exporter.txt` to a `.zsc`: in ZBrush open the
   **ZScript** palette, press **Load**, choose the `.txt`, then **Save As…**
   a `.zsc` (or use the ZScript compiler).
2. **Auto-load:** drop the `.zsc` into
   `Pixologic/ZBrush 2022/ZStartup/ZPlugs64/` so it loads on every launch.
   *Or* load it manually each session via **Preferences ▸ ZPlugin/ZScript**.
3. A **Bozzetto Exporter** subpalette appears in the **ZPlugin** palette.

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
2. **Set Output Folder** — browse *into* your target folder, type any
   filename, **Save** (only the folder is used).
3. **Detect Undo History** — confirms the plugin can read your undo counter and
   reports the number of stored steps. *Do this first.*
4. *(Optional)* set:
   - **Export Subdiv Level** — `0` keeps the current level; lower = smaller files.
   - **Every Nth Step** — subsample (e.g. `5` = every 5th step).
   - **Max Frames (0=all)** — cap the count; the stride is auto-derived.
   - **Filename Padding** — digits in the frame number (`4` → `sculpt_0001.obj`).
5. **Export Undo History** — writes the sequence.

### 3. Or capture stages manually
- **Capture Stage** exports the current state as the next frame. Use it as you
  sculpt, or as a fallback if undo stepping is constrained.
- **New Sequence (Reset)** sets the frame counter back to `1`.

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

## What still needs hardware verification (`//VERIFY`)

- **Undo Counter interface path** — the exact `Edit:Tool:…` token (the
  **Detect Undo History** button probes candidates and reports what it finds).
- That **setting the undo counter scrubs the geometry** to that step and is
  synchronous in a loop (if not, switch to the replay pattern).
- `Tool:Geometry:SDiv` set, the `ISlider` argument order, and numeric→string
  coercion in `StrMerge`.
- Stock **Decimation Master** control names in the fallback path.

### Confirmed working / fixed during testing
- The export pipeline runs and writes the OBJ sequence into the chosen folder.
- `MemReadString` writes into a target variable
  (`[MemReadString, block, var, offset]`) — fixed the "Incorrect Variable
  input type" error.
- Paths are converted to **forward slashes** on input (`slashify`, using
  `StrExtract`/`StrToAsc`) — fixed the backslash-stripping; those string ops work.
- `FileNameExtract` flag **`1`** (folder path) — fixed filenames coming out as
  `testsculpt_0001` (flag `3` had also kept the picked file's name).

### Known limitations
- **Set Output Folder** uses ZBrush's must-exist file dialog, so you select any
  existing file *inside* the target folder (only the folder is used; drop a file
  into an empty folder first). A folder-only picker via ZFileUtils is planned.
- ZBrush writes an **`.mtl`** next to each `.obj`. Bozzetto ignores non-mesh
  files, but to remove the clutter run a one-liner in the output folder:
  `del *.mtl` (Windows) or `rm *.mtl` (macOS/Linux). An optional in-ZBrush
  auto-delete (via ZFileUtils) can be added if wanted.

---

## Credits

- The memblock **"replay" pattern** for driving Decimation Master from ZScript
  is courtesy of **Marcus Civis** (`Batch_DM` on ZBrushCentral).
- [Bozzetto](https://github.com/vidarrapp/bozzetto) by vidarrapp.

## License

MIT — see [LICENSE](LICENSE).
