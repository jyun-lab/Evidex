"""Series management dialogs for the Qt app."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from evidex.core.fields import GCOL, LONG_FIELDS, feature_enabled
from evidex.core.record_table import save_record_rows
from evidex.core.series_table import (
    load_series_table,
    save_series_rows,
    series_manager_rows,
)
from evidex.core.i18n import t


class SeriesManagerDialog(QDialog):
    series_selected = Signal(str)

    LABELS = {
        "series_id": t("series.col.sid"),
        "experimenter": t("series.field.experimenter"),
        "period": t("series.field.period"),
        "objective": t("series.field.objective"),
        "claim": t("series.field.claim"),
        "established_knowns": t("series.field.established_knowns"),
        "unresolved": t("series.field.unresolved"),
        "evidence_docs": t("series.field.evidence_docs"),
        "my_assessment": t("series.field.my_assessment"),
    }
    LONG_FIELDS = {
        "objective",
        "claim",
        "established_knowns",
        "unresolved",
        "evidence_docs",
        "my_assessment",
    }

    def __init__(self, record_table, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("series.title.manager"))
        self.resize(1180, 680)
        self.setMinimumSize(960, 600)
        self.record_table = record_table
        self.record_mtime = record_table.mtime
        self.series_rows, self.series_fields, self.series_mtime = load_series_table(
            record_table.records_csv
        )
        self.rows_cache = []
        self.changed = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel(t("series.title.manager"))
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        note = QLabel(t("qt.common.group_experiment_records_by_series_id_to_review"))
        note.setStyleSheet("color: #667085;")
        head.addWidget(title)
        head.addWidget(note, stretch=1)
        root.addLayout(head)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget()
        self.table.setMinimumWidth(520)
        self.table.setMaximumWidth(680)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.itemSelectionChanged.connect(self.render_selected_detail)
        self.table.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #D0D7DE;
                alternate-background-color: #F6F8FA;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #2563EB;
                color: #FFFFFF;
                border-top: 1px solid #1D4ED8;
                border-bottom: 1px solid #1D4ED8;
            }
            QTableWidget::item:selected:!active {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
            QHeaderView::section {
                background: #EEF2F6;
                border: 1px solid #D0D7DE;
                padding: 6px;
                font-weight: 600;
            }
            """
        )
        splitter.addWidget(self.table)

        self.detail_panel = QWidget()
        self.detail_panel.setMinimumWidth(420)
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(12, 0, 0, 0)
        detail_layout.setSpacing(8)

        detail_head = QHBoxLayout()
        self.series_title = QLabel(t("qt.common.select_a_series"))
        self.series_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.series_edit_button = QPushButton(t("btn.edit_series_info"))
        self.series_delete_button = QPushButton(t("qt.common.delete_series"))
        self.series_delete_button.setStyleSheet("color: #B42318; border-color: #FDA29B;")
        self.series_edit_button.clicked.connect(
            lambda: self.edit_series(self.selected_sid() or "")
        )
        self.series_delete_button.clicked.connect(
            lambda: self.delete_series(self.selected_sid() or "")
        )
        detail_head.addWidget(self.series_title)
        detail_head.addStretch()
        detail_head.addWidget(self.series_edit_button)
        detail_head.addWidget(self.series_delete_button)
        detail_layout.addLayout(detail_head)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #667085;")
        detail_layout.addWidget(self.summary_label)

        self.grades_label = QLabel("")
        self.grades_label.setStyleSheet("color: #667085; font-weight: 600;")
        detail_layout.addWidget(self.grades_label)

        self.story_area = QScrollArea()
        self.story_area.setWidgetResizable(True)
        self.story_area.setFrameShape(QFrame.Shape.NoFrame)
        self.story_area.setMinimumHeight(140)
        self.story_page = QWidget()
        self.story_layout = QVBoxLayout(self.story_page)
        self.story_layout.setContentsMargins(0, 0, 0, 0)
        self.story_layout.setSpacing(8)
        self.story_area.setWidget(self.story_page)
        detail_layout.addWidget(self.story_area, stretch=1)

        self.runs_label = QLabel(t("qt.common.linked_experiments"))
        self.runs_label.setStyleSheet("color: #667085; font-weight: 700;")
        detail_layout.addWidget(self.runs_label)

        self.runs_table = QTableWidget()
        self.runs_table.setAlternatingRowColors(True)
        self.runs_table.setShowGrid(True)
        self.runs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.runs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.runs_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.runs_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.runs_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.runs_table.verticalHeader().setVisible(False)
        self.runs_table.verticalHeader().setDefaultSectionSize(30)
        self.runs_table.cellDoubleClicked.connect(self.open_run_from_current_table)
        detail_layout.addWidget(self.runs_table, stretch=1)

        splitter.addWidget(self.detail_panel)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, stretch=1)
        self.splitter = splitter

        footer = QHBoxLayout()
        new_button = QPushButton(t("series.title.new_prompt"))
        close_button = QPushButton(t("btn.close"))
        new_button.clicked.connect(self.new_series)
        close_button.clicked.connect(self.accept)
        footer.addWidget(new_button)
        footer.addStretch()
        footer.addWidget(close_button)
        root.addLayout(footer)

        self.refresh_table()
        QApplication.instance().processEvents()
        self.splitter.setSizes([560, 420])

    def refresh_table(self, selected_sid=None):
        self.rows_cache = series_manager_rows(
            self.record_table.rows,
            self.series_rows,
            feature_enabled("grading"),
        )
        columns = [("sid", t("series.col.sid")), ("n", t("series.col.n_runs")), ("period", t("series.field.period"))]
        if feature_enabled("grading"):
            columns.append(("grades", t("series.col.grade_seq")))
        columns.append(("objective", t("series.field.objective")))

        self.table.blockSignals(True)
        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setRowCount(len(self.rows_cache))
        self.table.setHorizontalHeaderLabels([label for _key, label in columns])
        for row_index, row in enumerate(self.rows_cache):
            for column_index, (key, _label) in enumerate(columns):
                value = row.get(key, "")
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row["sid"])
                self.table.setItem(row_index, column_index, item)
        header = self.table.horizontalHeader()
        for column_index, (key, _label) in enumerate(columns):
            if key == "objective":
                header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Fixed)
                widths = {
                    "sid": 110,
                    "n": 70,
                    "period": 150,
                    "grades": 110,
                }
                self.table.setColumnWidth(column_index, widths.get(key, 100))
        header.setStretchLastSection(False)
        self.table.blockSignals(False)

        if self.rows_cache:
            target = 0
            if selected_sid:
                for index, row in enumerate(self.rows_cache):
                    if row["sid"] == selected_sid:
                        target = index
                        break
            self.table.selectRow(target)
            self.render_selected_detail()
        else:
            self.render_empty_detail(t("qt.common.there_are_no_series_yet_create_one_or"))

    def selected_sid(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def render_selected_detail(self):
        sid = self.selected_sid()
        if sid is None:
            self.render_empty_detail(t("qt.common.select_a_series_from_the_list_on_the"))
            return
        row = next((item for item in self.rows_cache if item["sid"] == sid), None)
        if row is None:
            self.render_empty_detail(t("qt.common.series_information_could_not_be_displayed"))
            return
        self.render_detail(row)

    def clear_story(self):
        while self.story_layout.count():
            item = self.story_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def render_empty_detail(self, message):
        self.clear_story()
        self.series_title.setText(t("qt.common.select_a_series"))
        self.summary_label.setText(message)
        self.grades_label.setText("")
        self.runs_label.setText(t("qt.common.linked_experiments"))
        self.series_edit_button.setEnabled(False)
        self.series_delete_button.setEnabled(False)
        self.runs_table.clear()
        self.runs_table.setRowCount(0)
        self.runs_table.setColumnCount(0)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setStyleSheet("color: #667085; padding: 8px;")
        self.story_layout.addWidget(label)
        self.story_layout.addStretch()

    def render_detail(self, row):
        self.clear_story()
        sid = row["sid"]
        runs = row["runs"]
        series_row = row["srow"]

        self.series_title.setText(sid)
        self.series_edit_button.setEnabled(True)
        self.series_delete_button.setEnabled(True)
        self.summary_label.setText(t("series.label.summary", n=row["n"], period=row["period"]))

        if feature_enabled("grading"):
            self.grades_label.setText(t("qt.series.grade_sequence", grades=row["grades"]))
            self.grades_label.setVisible(True)
        else:
            self.grades_label.setText("")
            self.grades_label.setVisible(False)

        if series_row:
            for key in (
                "objective",
                "claim",
                "established_knowns",
                "unresolved",
                "my_assessment",
            ):
                value = (series_row.get(key, "") or "").strip()
                if not value:
                    continue
                self.story_layout.addWidget(
                    self.detail_text_block(self.LABELS.get(key, key), value)
                )
        else:
            missing = QLabel(t("qt.common.not_registered_in_series_csv_use_edit_series"))
            missing.setWordWrap(True)
            missing.setStyleSheet("color: #667085;")
            self.story_layout.addWidget(missing)
        self.story_layout.addStretch()

        self.runs_label.setText(t("series.label.runs", n=len(runs)))
        self.populate_runs_table(runs)

    def detail_text_block(self, label, value):
        frame = QFrame()
        frame.setObjectName("seriesDetailBlock")
        frame.setStyleSheet(
            """
            QFrame#seriesDetailBlock {
                border: 1px solid #D0D7DE;
                border-radius: 8px;
                background: #FFFFFF;
            }
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        title = QLabel(label)
        title.setStyleSheet("color: #667085; font-weight: 700;")
        body = QLabel(value)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(title)
        layout.addWidget(body)
        return frame

    def populate_runs_table(self, runs):
        table = self.runs_table
        columns = [("run_id", "run_id"), ("date", t("schema_editor.str41")), ("title", t("qt.common.title"))]
        if feature_enabled("grading"):
            columns.append(("grade", "Grade"))
        columns.append(("result_summary", t("pane.section.result_summary")))
        table.clear()
        table.setColumnCount(len(columns))
        table.setRowCount(len(runs))
        table.setHorizontalHeaderLabels([label for _key, label in columns])
        for row_index, run in enumerate(runs):
            for column_index, (key, _label) in enumerate(columns):
                value = run.get(key, "")
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, run.get("run_id", ""))
                if key == "grade":
                    item.setForeground(QColor(GCOL.get(str(value).upper(), "#344054")))
                table.setItem(row_index, column_index, item)
        header = table.horizontalHeader()
        for column_index, (key, _label) in enumerate(columns):
            if key == "result_summary":
                header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Interactive)
                widths = {
                    "run_id": 100,
                    "date": 90,
                    "title": 140,
                    "grade": 70,
                }
                table.setColumnWidth(column_index, widths.get(key, 100))

    def open_run_from_current_table(self, row, _column):
        item = self.runs_table.item(row, 0)
        run_id = item.data(Qt.ItemDataRole.UserRole) if item else ""
        if run_id:
            self.series_selected.emit(run_id)
            self.accept()

    def new_series(self):
        series_id, ok = QInputDialog.getText(
            self,
            t("series.title.new_prompt"),
            t("qt.common.enter_a_series_id"),
        )
        series_id = series_id.strip()
        if not ok or not series_id:
            return
        existing = {row["sid"].casefold() for row in self.rows_cache}
        if series_id.casefold() in existing:
            QMessageBox.warning(self, t("msg.duplicate"), t("series.msg.duplicate", sid=series_id))
            return
        self.edit_series(series_id)

    def edit_series(self, series_id):
        current = next(
            (
                row for row in self.series_rows
                if (row.get("series_id", "") or "").strip() == series_id
            ),
            None,
        )
        is_new = current is None
        data = dict(current) if current else {field: "" for field in self.series_fields}
        data["series_id"] = series_id
        dialog = SeriesEditDialog(data, self.series_fields, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.values()
        original = dict(current) if current is not None else None
        if is_new:
            self.series_rows.append(updated)
        else:
            current.update(updated)
        try:
            self.series_mtime = save_series_rows(
                self.record_table.records_csv,
                self.series_rows,
                self.series_fields,
                self.series_mtime,
            )
        except Exception as error:
            if is_new and updated in self.series_rows:
                self.series_rows.remove(updated)
            if not is_new and current is not None and original is not None:
                current.clear()
                current.update(original)
            QMessageBox.critical(self, t("data.msg.save_error"), str(error))
            return
        self.changed = True
        self.refresh_table(series_id)

    def delete_series(self, series_id):
        runs = [
            row for row in self.record_table.rows
            if (row.get("series_id", "") or "").strip() == series_id
        ]
        if runs:
            message = (
                t("series.msg.confirm_delete_with_runs", sid=series_id, n=len(runs))
            )
        else:
            message = t("series.msg.confirm_delete", sid=series_id)
        answer = QMessageBox.question(
            self,
            t("qt.common.delete_series"),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        original_runs = [dict(row) for row in runs]
        original_series_rows = list(self.series_rows)
        try:
            for row in runs:
                row["series_id"] = ""
            self.record_mtime = save_record_rows(
                self.record_table.records_csv,
                self.record_table.rows,
                self.record_table.fields,
                self.record_mtime,
            )
            self.series_rows = [
                row for row in self.series_rows
                if (row.get("series_id", "") or "").strip() != series_id
            ]
            self.series_mtime = save_series_rows(
                self.record_table.records_csv,
                self.series_rows,
                self.series_fields,
                self.series_mtime,
            )
        except Exception as error:
            for row, original in zip(runs, original_runs):
                row.clear()
                row.update(original)
            self.series_rows = original_series_rows
            QMessageBox.critical(self, t("qt.common.delete_error"), str(error))
            return
        self.changed = True
        self.refresh_table()


class SeriesEditDialog(QDialog):
    def __init__(self, row, fields, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("series.title.edit", sid=row.get("series_id", "")))
        self.resize(680, 560)
        self.row = row
        self.fields = list(fields)
        self.widgets = {}

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll.setWidget(page)
        root.addWidget(scroll, stretch=1)

        sid = QLabel(row.get("series_id", ""))
        sid.setStyleSheet("font-weight: 700;")
        form.addRow(t("series.col.sid"), sid)
        for field in self.fields:
            if field == "series_id":
                continue
            widget = self.create_widget(field, row.get(field, ""))
            self.widgets[field] = widget
            form.addRow(SeriesManagerDialog.LABELS.get(field, field), widget)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel_button = QPushButton(t("btn.cancel"))
        save_button = QPushButton(t("btn.save"))
        save_button.setDefault(True)
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)
        footer.addWidget(cancel_button)
        footer.addWidget(save_button)
        root.addLayout(footer)

    def create_widget(self, field, value):
        if field in SeriesManagerDialog.LONG_FIELDS:
            widget = QTextEdit()
            widget.setPlainText(value)
            widget.setMinimumHeight(80)
            return widget
        widget = QLineEdit()
        widget.setText(value)
        return widget

    def values(self):
        data = dict(self.row)
        for field, widget in self.widgets.items():
            if isinstance(widget, QTextEdit):
                value = widget.toPlainText()
            else:
                value = widget.text()
            data[field] = value.strip()
        return data
