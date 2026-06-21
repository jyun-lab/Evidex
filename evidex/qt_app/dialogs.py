"""Backward-compatible re-exports for Qt dialog classes.

The actual implementations have moved to dedicated modules:
- series_dialog.py  (SeriesManagerDialog, SeriesEditDialog)
- steps_dialog.py   (StepsEditorDialog, StepEditDialog)
- record_dialog.py  (RecordEditDialog)
"""

from .record_dialog import RecordEditDialog
from .series_dialog import SeriesEditDialog, SeriesManagerDialog
from .steps_dialog import StepEditDialog, StepsEditorDialog

__all__ = [
    "RecordEditDialog",
    "SeriesEditDialog",
    "SeriesManagerDialog",
    "StepEditDialog",
    "StepsEditorDialog",
]
