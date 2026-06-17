# Evidex

![Evidex logo](docs/assets/evidex-logo.svg)

**Turn scattered lab files into searchable experiment evidence.**

Evidex is a local-first desktop app for researchers who have instrument CSVs,
analysis spreadsheets, photos, notes, and an Excel-like ledger scattered across
folders. It keeps the original files where they are, then gives you a searchable
record of what happened, which files belong together, and what the data looked
like.

No server. No Docker. No cloud account. Just local files.

![Evidex desktop app showing experiment records, waveform preview, and linked files](docs/assets/screenshot-main.png)

> Status: pre-release. Evidex is usable, but the public v0.1 release is still
> being polished.

## The Problem

Many small labs already have the data. The hard part is finding it again.

- A raw CSV is in one folder.
- The processed spreadsheet is somewhere else.
- Photos and figures live in a separate directory.
- Notes are in a notebook or a text field.
- The experiment ledger slowly turns into a spreadsheet nobody wants to touch.

Evidex is for the middle ground where Excel is becoming painful, but a full ELN,
LIMS, or server-based platform is too heavy.

## What Evidex Does

- Search and filter experiment records stored in local CSV ledgers
- Link raw CSVs, analysis files, photos, notebooks, and other attachments
- Preview time-series CSV waveforms without modifying the source file
- Preview linked photos and figures from the record detail pane
- Create custom CSV reading rules from the Pack Manager, without writing Python
- Optionally record procedure steps for each experiment
- Optionally group related records into research series
- Switch between English and Japanese UI text
- Build a portable Windows executable with PyInstaller

## Core Idea

Evidex separates your experiment context into three layers.

| Layer | What it contains |
|---|---|
| Original files | Instrument CSVs, spreadsheets, photos, notebooks |
| Search metadata | `runs.csv`, `steps.csv`, `series.csv` |
| Instrument packs | CSV reading rules and optional workflow features |

Original files are not moved or rewritten. Evidex stores paths and metadata so
you can search, inspect, and reopen the files later.

## Try the Synthetic Demo

The files in [`examples/demo`](examples/demo/) are fully synthetic. They contain
no real researchers, lab records, unpublished results, or instrument data. The
demo includes oscilloscope-style sine-wave CSV captures, a generated attachment
image, and a demo-only pack under `examples/demo/packs/oscilloscope_demo`.

1. Copy `examples/demo/` to a temporary folder.
2. Run Evidex.
3. Open the copied `runs.csv`.
4. Select the `oscilloscope_demo` pack if you want screenshot-oriented labels.
5. Select a record.
6. Preview the linked signal CSV and inspect linked files from the detail pane.

Do not replace the demo files with real laboratory data before committing to
Git.

## Run From Source

Python 3.8 or newer is required.

```bash
python evidex_app.py
```

Optional packages improve the interface and waveform display:

```bash
python -m pip install ttkbootstrap matplotlib
```

Evidex can still start with standard `tkinter` when optional packages are not
available, although graph previews need `matplotlib`.

## Create a CSV Pack Without Programming

If your measurement CSV has a normal header row, you can configure it from the
Pack Manager.

1. Open **File > Pack Manager**.
2. Click **+ New Pack** and enter a pack name.
3. Go to **CSV & Waveform**.
4. Click **Choose Sample CSV**.
5. Pick the X-axis column, such as time, wavelength, or voltage.
6. Pick one or more graph columns, such as temperature, pressure, or intensity.
7. Enter units if needed.
8. Click **Apply CSV Settings**.
9. Click **Test Import**.
10. Save the pack.

Comma, tab, and semicolon delimiters are detected automatically. Files with
extra information above the header can be handled with **Rows to skip**.

These settings are saved as:

```text
packs/<pack_name>/adapter_config.json
```

Some specialized instruments need a custom Python reader instead. Those packs
use `adapter.py`; their CSV mapping is defined in code and is not edited through
the no-code column mapping UI.

## Data Safety

Evidex is designed around local ownership of research files.

- It does not modify original raw CSVs, spreadsheets, or photos.
- Search metadata is stored in plain CSV files.
- Before writing a metadata CSV, Evidex creates a timestamped backup.
- User packs and local ledgers are excluded from Git by default.

Never publish:

- real laboratory records
- unpublished results or interpretations
- personal names or private researcher identifiers
- internal server paths or shared-folder paths
- real instrument CSVs, spreadsheets, photos, or notebooks
- local user packs
- build output under `build/` or `dist/`

See [Release Checklist](docs/RELEASE_CHECKLIST.md) before making a
repository public.

## What Evidex Is Not

Evidex is intentionally small. It is not trying to replace a full ELN, LIMS, or
scientific plotting suite.

It does not currently provide:

- multi-user permissions or real-time collaboration
- electronic signatures or regulatory audit trails
- sample, reagent, or inventory management
- cloud synchronization
- advanced statistical analysis
- publication-ready figure production

The goal is to preserve the connection between a result, its raw files, and the
experiment record that explains it.

## Instrument Packs

Public builds include a generic time-series pack:

- `generic_ts`: a simple starting point for CSV data with one X column and one
  or more measurement columns

Private labs can keep instrument-specific workflows as local user packs:

```text
packs/<pack_name>/
```

Packs can enable optional features such as procedure steps, research series,
grading, baseline correction, waveform modes, and channel groups.

## Build a Windows Executable

Install build dependencies:

```bash
python -m pip install pyinstaller ttkbootstrap matplotlib
```

Then run:

```bash
build.bat
```

or:

```bash
python build.py
```

Build output is created as `dist/Evidex.exe` and is intentionally excluded from
Git.

## License

Evidex is released under the [MIT License](LICENSE).

Dependency licenses are separate. The initial public release is focused on the
Tkinter app; Qt/PySide6 migration work is being kept outside the public main
branch for now.

## Project Status

The current stable UI is the Tkinter desktop app launched with:

```bash
python evidex_app.py
```

A Qt interface is being explored separately, but the initial public release is
focused on making the Tkinter version useful, safe, and easy to try with the
synthetic demo.

Current priorities:

1. Public v0.1 release cleanup
2. README screenshots and a short demo GIF
3. Pack Manager onboarding
4. Better photo and figure browsing
5. Downloadable Windows releases

## Related Notes

- [Synthetic demo data](examples/demo/)
- [Release checklist](docs/RELEASE_CHECKLIST.md)



