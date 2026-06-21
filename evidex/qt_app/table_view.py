"""Table display and interaction for the Qt main window."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QMenu,
    QMessageBox,
    QTableWidgetItem,
)

from evidex.core.attachments import split_paths
from evidex.core.fields import GCOL
from evidex.core.record_table import (
    load_record_table,
    resolve_record_file_path,
    row_values,
)
from evidex.core.series_table import load_series_table
from evidex.core.steps_table import load_steps_table

from .popout import DetailPopoutWindow


class TableMixin:
    """テーブル表示・操作・データ読み込み。"""

    def reload_records(self):
        try:
            self.record_table = load_record_table()
        except Exception as error:
            QMessageBox.critical(self, "読み込みエラー", str(error))
            return

        self.steps_by_run = {}
        if self.steps_enabled:
            try:
                self.steps_by_run, _sf, _sm = load_steps_table(
                    self.record_table.records_csv
                )
            except Exception:
                self.steps_by_run = {}

        self.series_rows = []
        if self.series_enabled:
            try:
                self.series_rows, _sf, _sm = load_series_table(
                    self.record_table.records_csv
                )
            except Exception:
                self.series_rows = []

        self._refresh_filter_choices()
        self.apply_search()
        self._refresh_presets()
        self.build_nav()

    def populate_table(self):
        columns = self.record_table.columns
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setRowCount(len(self.filtered_rows))
        self.table.setHorizontalHeaderLabels([column.label for column in columns])

        for column_index, column in enumerate(columns):
            self.table.setColumnWidth(column_index, column.width)

        grade_col_index = None
        for ci, col in enumerate(columns):
            if col.key == "grade":
                grade_col_index = ci
                break

        for row_index, row in enumerate(self.filtered_rows):
            try:
                source_index = self.record_table.rows.index(row)
            except ValueError:
                continue
            values = row_values(row, columns)
            grade_value = (row.get("grade", "") or "").strip().upper()
            grade_color = GCOL.get(grade_value) if grade_value else None
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, source_index)
                if grade_color and column_index == grade_col_index:
                    item.setForeground(QColor(grade_color))
                self.table.setItem(row_index, column_index, item)

        header = self.table.horizontalHeader()
        stretch_keys = {"title", "result_summary", "notes"}
        for column_index, column in enumerate(columns):
            if column.key in stretch_keys:
                header.setSectionResizeMode(
                    column_index, QHeaderView.ResizeMode.Stretch
                )
            else:
                header.setSectionResizeMode(
                    column_index, QHeaderView.ResizeMode.Interactive
                )
        header.setStretchLastSection(False)
        self.table.setSortingEnabled(True)
        self._apply_grade_row_colors()
        total = len(self.record_table.rows)
        shown = len(self.filtered_rows)
        query = self.search_input.text().strip()
        if query or self.nav_view is not None:
            self.count_label.setText(f"{shown} / {total} 件")
        else:
            self.count_label.setText(f"{total} 件")
        self.statusBar().showMessage(
            f"{self.record_table.records_csv}  |  {shown} / {total} 件"
        )
        if self.filtered_rows:
            self.table.selectRow(0)
        else:
            self.show_empty_detail()
        self.table.blockSignals(False)
        if self.filtered_rows:
            self.show_selected_record()

    def _filtered_index_for_table_row(self, table_row):
        if self.record_table is None or not (0 <= table_row < self.table.rowCount()):
            return None
        first_item = self.table.item(table_row, 0)
        source_index = (
            first_item.data(Qt.ItemDataRole.UserRole)
            if first_item is not None
            else None
        )
        try:
            source_row = self.record_table.rows[int(source_index)]
        except (TypeError, ValueError, IndexError):
            return None
        for index, row in enumerate(self.filtered_rows):
            if row is source_row:
                return index
        try:
            return self.filtered_rows.index(source_row)
        except ValueError:
            return None

    def _on_table_double_click(self, model_index):
        index = self._filtered_index_for_table_row(model_index.row())
        if index is not None:
            self.open_detail(index)

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if item is None:
            return
        self.table.selectRow(item.row())
        self.show_selected_record()

        menu = QMenu(self)
        menu.addAction("詳細を開く", self._open_selected_detail)
        menu.addAction("記録を編集", self.edit_selected_record)
        if self.steps_enabled:
            menu.addAction("工程を編集", self.edit_selected_steps)
        menu.addSeparator()
        menu.addAction(
            "raw_path を開く",
            lambda: self._open_selected_path("raw_path"),
        )
        menu.addAction(
            "excel_path を開く",
            lambda: self._open_selected_path("excel_path"),
        )
        menu.addAction("パスをコピー", self._copy_selected_paths)
        menu.addSeparator()
        menu.addAction("削除", self.delete_selected_record)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _open_selected_path(self, column):
        if self.current_row is None:
            return
        paths = split_paths(self.current_row.get(column, ""))
        if not paths:
            QMessageBox.information(
                self,
                "情報",
                f"{column} にファイルが登録されていません。",
            )
            return
        resolved = resolve_record_file_path(
            paths[0],
            records_csv=self.record_table.records_csv,
        )
        if resolved.exists():
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(resolved))
            )
        else:
            QMessageBox.warning(
                self,
                "ファイルが見つかりません",
                str(resolved),
            )

    def _copy_selected_paths(self):
        if self.current_row is None:
            return
        paths = split_paths(self.current_row.get("raw_path", ""))
        if paths:
            QApplication.clipboard().setText("\n".join(paths))
            self.statusBar().showMessage(
                f"パスをコピーしました ({len(paths)} 件)",
                3000,
            )
        else:
            QMessageBox.information(self, "情報", "raw_path が空です。")

    def _open_selected_detail(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        index = self._filtered_index_for_table_row(selected[0].row())
        if index is not None:
            self.open_detail(index)

    def open_detail(self, idx):
        if not (0 <= idx < len(self.filtered_rows)):
            return
        window = DetailPopoutWindow(self, idx)
        self._detail_windows.append(window)
        window.destroyed.connect(
            lambda _object=None, detail_window=window:
            self._forget_detail_window(detail_window)
        )
        window.show()

    def _forget_detail_window(self, window):
        if window in self._detail_windows:
            self._detail_windows.remove(window)

    def select_run_id(self, run_id):
        if not run_id:
            return
        for row_index, row in enumerate(self.filtered_rows):
            if row.get("run_id", "") == run_id:
                self.table.selectRow(row_index)
                self.show_selected_record()
                return
