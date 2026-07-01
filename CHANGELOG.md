# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Single version source at `evidex.__version__`
- `--data`, `EVIDEX_HOME`, and remembered ledger-folder resolution
- File menu action to choose the ledger folder for the next startup
- Atomic write helper for ledger CSV, settings JSON, and user-pack JSON files
- Windows CI job for the public test suite

### Fixed

- Backup pruning now keeps 100 generations independently for each ledger prefix
- README download links now point to the latest Releases page instead of versioned exe URLs
- Tests are isolated from local settings and private user packs
- GUI tests in CI no longer hide failures with `|| true`

### Changed

- Package metadata now reads the version dynamically from `evidex.__version__`
- Installed-package default ledger location is now `~/Evidex` instead of the package directory

## [0.2.0] — 2026-06-21

### Added

- GitHub Actions release workflow: tag `v*` triggers test, PyInstaller build (tkinter + Qt), and GitHub Release with artifacts
- `build.py` flags: `--qt` for Qt exe, `--version` to append version to exe name
- PySide6 LGPL license notice bundled with Qt exe builds
- Demo data (oscilloscope pack, signals, images) bundled in exe and auto-extracted on first run
- Qt exe now calls `extract_bundled_assets()` on startup (same as tkinter)

### Fixed

- `pyproject.toml`: removed `License :: OSI Approved :: MIT License` classifier that conflicted with PEP 639 `license = "MIT"` field (broke `pip install` on latest setuptools)

### Changed

- Qt backend is now the recommended default
- Codebase-wide refactoring for maintainability (Steps 7–16):
  - tkinter `main.py`: `_build()` split into focused builder methods
  - Qt `main_window.py`: split from 5619 → 658 lines via 6 Mixin modules (DetailMixin, NavigationMixin, FilterMixin, ThemeMixin, TableMixin, RecordOpsMixin)
  - Qt `schema_editor_dialog.py`: closure → class conversion, then 4 Mixin split (1241 → 168 lines)
  - tkinter `views/schema_editor.py`: closure → class conversion, then 4 Mixin split (1490 → 439 lines)
  - Qt `dialogs.py`: split into `series_dialog.py`, `steps_dialog.py`, `record_dialog.py` with re-export module
  - Qt `__init__` builder method split
- All source files now under 700 lines

## [0.1.0] — 2026-05-01

### Added

- Initial release
- tkinter GUI with ttkbootstrap theme support
- Qt (PySide6) GUI backend
- Search and filter experiment records from local CSV ledgers
- Waveform preview for time-series CSVs
- Image preview in detail pane
- Pack Manager GUI for defining CSV reading rules
- Procedure steps tracking per experiment
- Research series grouping
- English / Japanese UI
- `python -m evidex` entry point with `--qt` / `--tk` flags
- `pyproject.toml` with optional dependencies `[qt]` and `[tk]`
- GitHub Actions CI (tkinter: Python 3.9/3.12/3.13, Qt: Python 3.10/3.12)

[0.2.0]: https://github.com/jyun-lab/Evidex/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jyun-lab/Evidex/releases/tag/v0.1.0
