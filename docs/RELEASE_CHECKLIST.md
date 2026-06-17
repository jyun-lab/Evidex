# Public Release Checklist

Use this checklist before making the repository public on GitHub. The goal is
to publish Evidex itself without accidentally sharing real lab data, private
paths, or local-only development files.

## Never Publish

- Real laboratory records, researcher names, student names, or patient-like IDs
- Unpublished results, interpretations, or instrument output
- Internal server paths, shared-drive paths, NAS names, or absolute local paths
- Real instrument CSVs, spreadsheets, photos, notebooks, or exported figures
- `evidex_settings.json`
- Root-level `runs.csv`, `steps.csv`, or `series.csv`
- Local user packs under `packs/`
- Build output under `build/` or `dist/`
- Private handover notes, planning files, and one-off migration scripts

## Safe To Publish

- Source code for the Tkinter app
- Synthetic demo data under `examples/demo/`
- Public documentation under `docs/`
- Original project artwork under `docs/assets/`
- Tests that do not depend on private lab data
- Build scripts, as long as they do not contain private paths or credentials

## Before First Push

1. Confirm `.gitignore` excludes local ledgers, packs, settings, build output,
   private notes, and Qt migration files.
2. Confirm `LICENSE` exists and matches the license named in `README.md`.
3. Confirm `examples/demo/` contains only synthetic data.
4. Search the repository for personal names, lab names, server names, absolute
   local paths, and private instrument identifiers.
5. Run the test suite.
6. Start Evidex with the synthetic demo and check the main flows.
7. Add one clean screenshot to the README after the UI is ready.

## Suggested Public Files

- `README.md`
- `LICENSE`
- `.gitignore`
- `evidex_app.py`
- `evidex/`
- `examples/demo/`
- `tests/`
- `docs/`
- `build.py`
- `build.bat`

## After Publishing

If private information is accidentally published, deleting it in a later commit
is not enough because Git history still contains it. Make the repository
private immediately, rewrite the affected history if needed, rotate any exposed
secrets, and only publish again after checking the repository from a fresh clone.
