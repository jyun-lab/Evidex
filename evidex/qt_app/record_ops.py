"""Record CRUD operations for the Qt main window."""

from PySide6.QtWidgets import QDialog, QMessageBox

from evidex.core.record_table import (
    default_new_record,
    save_record_rows,
    validate_record_update,
)

from .dialogs import (
    RecordEditDialog,
    SeriesManagerDialog,
    StepsEditorDialog,
)


class RecordOpsMixin:
    """実験記録の編集・追加・削除操作。"""

    def edit_run(self, row):
        self.current_row = row
        self.edit_selected_record()

    def open_steps_editor(self, run_id):
        if self.record_table is None:
            return
        row = next(
            (
                item for item in self.record_table.rows
                if item.get("run_id", "") == run_id
            ),
            None,
        )
        if row is None:
            return
        self.current_row = row
        self.edit_selected_steps()

    def edit_selected_record(self):
        if self.current_row is None or self.record_table is None:
            QMessageBox.information(
                self,
                "実験記録を編集",
                "編集する実験記録を選択してください。",
            )
            return
        dialog = RecordEditDialog(
            self.current_row,
            self.record_table.fields,
            self,
            base_dir=self.record_table.records_csv.parent,
            title=f"実験記録を編集: {self.current_row.get('run_id', '')}",
            series_choices=self._known_series(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.values()
        original = dict(self.current_row)
        try:
            validate_record_update(
                self.current_row,
                updated,
                self.record_table.rows,
            )
            self.current_row.update(updated)
            save_record_rows(
                self.record_table.records_csv,
                self.record_table.rows,
                self.record_table.fields,
                self.record_table.mtime,
            )
        except Exception as error:
            self.current_row.clear()
            self.current_row.update(original)
            QMessageBox.critical(self, "保存エラー", str(error))
            return
        selected_run_id = updated.get("run_id", "")
        self.reload_records()
        self.select_run_id(selected_run_id)
        self.statusBar().showMessage(
            f"実験記録「{selected_run_id}」を保存しました。", 5000
        )

    def add_new_record(self):
        if self.record_table is None:
            return
        row = default_new_record(
            self.record_table.rows,
            self.record_table.fields,
        )
        dialog = RecordEditDialog(
            row,
            self.record_table.fields,
            self,
            base_dir=self.record_table.records_csv.parent,
            title="新しい実験記録を追加",
            series_choices=self._known_series(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.values()
        try:
            validate_record_update(
                None,
                updated,
                self.record_table.rows,
            )
            self.record_table.rows.append(updated)
            save_record_rows(
                self.record_table.records_csv,
                self.record_table.rows,
                self.record_table.fields,
                self.record_table.mtime,
            )
        except Exception as error:
            if updated in self.record_table.rows:
                self.record_table.rows.remove(updated)
            QMessageBox.critical(self, "保存エラー", str(error))
            return
        selected_run_id = updated.get("run_id", "")
        self.reload_records()
        self.select_run_id(selected_run_id)
        self.statusBar().showMessage(
            f"実験記録「{selected_run_id}」を追加しました。", 5000
        )

    def delete_selected_record(self):
        if self.current_row is None or self.record_table is None:
            QMessageBox.information(
                self,
                "実験記録を削除",
                "削除する実験記録を選択してください。",
            )
            return
        run_id = self.current_row.get("run_id", "") or "(IDなし)"
        answer = QMessageBox.question(
            self,
            "実験記録を削除",
            f"実験記録「{run_id}」を削除しますか？\n\n"
            "この操作は runs.csv から記録を削除します。\n"
            "削除前のCSVは backup フォルダに保存されます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        row = self.current_row
        try:
            self.record_table.rows.remove(row)
            save_record_rows(
                self.record_table.records_csv,
                self.record_table.rows,
                self.record_table.fields,
                self.record_table.mtime,
            )
        except Exception as error:
            if row not in self.record_table.rows:
                self.record_table.rows.append(row)
            QMessageBox.critical(self, "削除エラー", str(error))
            return

        self.reload_records()
        self.statusBar().showMessage(
            f"実験記録「{run_id}」を削除しました。", 5000
        )

    def edit_selected_steps(self):
        if self.current_row is None or self.record_table is None:
            QMessageBox.information(
                self,
                "工程を編集",
                "工程を編集する実験記録を選択してください。",
            )
            return
        run_id = self.current_row.get("run_id", "").strip()
        if not run_id:
            QMessageBox.information(
                self,
                "工程を編集",
                "run_id がない記録の工程は編集できません。",
            )
            return
        dialog = StepsEditorDialog(
            run_id,
            self.record_table.records_csv,
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.statusBar().showMessage(
                f"工程「{run_id}」を保存しました。", 5000
            )

    def open_series_manager(self):
        if self.record_table is None:
            return
        dialog = SeriesManagerDialog(self.record_table, self)
        dialog.target_run_id = ""
        dialog.series_selected.connect(
            lambda run_id: setattr(dialog, "target_run_id", run_id)
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.reload_records()
            if getattr(dialog, "target_run_id", ""):
                self.select_run_id(dialog.target_run_id)
            self.statusBar().showMessage("シリーズ管理の変更を反映しました。", 5000)
