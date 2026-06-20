from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
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
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from evidex.core.fields import (
    ACTION_CHOICES,
    CHOICES,
    GCOL,
    HIDDEN_EDIT_FIELDS,
    LONG_FIELDS,
    STEP_FORM,
    feature_enabled,
    get_label,
)
from evidex.core.record_table import save_record_rows, validate_record_update
from evidex.core.series_table import (
    load_series_table,
    save_series_rows,
    series_manager_rows,
)
from evidex.core.steps_table import (
    load_steps_table,
    save_steps_table,
    validate_step_update,
)

from .widgets import FilePathEditor, ScrollSafeComboBox


class SeriesManagerDialog(QDialog):
    series_selected = Signal(str)

    LABELS = {
        "series_id": "シリーズID",
        "experimenter": "実験者",
        "period": "期間",
        "objective": "目的",
        "claim": "主張",
        "established_knowns": "確立したこと",
        "unresolved": "未解決",
        "evidence_docs": "根拠文書",
        "my_assessment": "自分の評価",
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
        self.setWindowTitle("シリーズ管理")
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
        title = QLabel("シリーズ管理")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        note = QLabel("series_id ごとに実験記録をまとめ、研究の目的や主張を確認できます。")
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
        self.series_title = QLabel("シリーズを選択")
        self.series_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.series_edit_button = QPushButton("シリーズ情報を編集")
        self.series_delete_button = QPushButton("シリーズを削除")
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

        self.runs_label = QLabel("所属実験")
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
        new_button = QPushButton("新規シリーズ")
        close_button = QPushButton("閉じる")
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
        columns = [("sid", "シリーズID"), ("n", "実験数"), ("period", "期間")]
        if feature_enabled("grading"):
            columns.append(("grades", "Grade推移"))
        columns.append(("objective", "目的"))

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
            self.render_empty_detail("シリーズがまだありません。新規シリーズを作成するか、実験記録に series_id を設定してください。")

    def selected_sid(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def render_selected_detail(self):
        sid = self.selected_sid()
        if sid is None:
            self.render_empty_detail("左の一覧からシリーズを選択してください。")
            return
        row = next((item for item in self.rows_cache if item["sid"] == sid), None)
        if row is None:
            self.render_empty_detail("シリーズ情報を表示できません。")
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
        self.series_title.setText("シリーズを選択")
        self.summary_label.setText(message)
        self.grades_label.setText("")
        self.runs_label.setText("所属実験")
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
        self.summary_label.setText(f"全{row['n']}実験  |  期間 {row['period']}")

        if feature_enabled("grading"):
            self.grades_label.setText(f"Grade推移: {row['grades']}")
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
            missing = QLabel("series.csvに未登録です。「シリーズ情報を編集」で作成できます。")
            missing.setWordWrap(True)
            missing.setStyleSheet("color: #667085;")
            self.story_layout.addWidget(missing)
        self.story_layout.addStretch()

        self.runs_label.setText(f"所属実験 ({len(runs)}件)")
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
        columns = [("run_id", "run_id"), ("date", "日付"), ("title", "タイトル")]
        if feature_enabled("grading"):
            columns.append(("grade", "Grade"))
        columns.append(("result_summary", "結果要約"))
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
            "新規シリーズ",
            "シリーズIDを入力してください。",
        )
        series_id = series_id.strip()
        if not ok or not series_id:
            return
        existing = {row["sid"].casefold() for row in self.rows_cache}
        if series_id.casefold() in existing:
            QMessageBox.warning(self, "重複", f"シリーズ {series_id} は既に存在します。")
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
            QMessageBox.critical(self, "保存エラー", str(error))
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
                f"シリーズ {series_id} には {len(runs)} 件の実験が紐づいています。\n"
                "削除すると、それらの実験の series_id は空欄になります。続けますか?"
            )
        else:
            message = f"シリーズ {series_id} を削除しますか?"
        answer = QMessageBox.question(
            self,
            "シリーズを削除",
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
            QMessageBox.critical(self, "削除エラー", str(error))
            return
        self.changed = True
        self.refresh_table()


class SeriesEditDialog(QDialog):
    def __init__(self, row, fields, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"シリーズ情報を編集: {row.get('series_id', '')}")
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
        form.addRow("シリーズID", sid)
        for field in self.fields:
            if field == "series_id":
                continue
            widget = self.create_widget(field, row.get(field, ""))
            self.widgets[field] = widget
            form.addRow(SeriesManagerDialog.LABELS.get(field, field), widget)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel_button = QPushButton("キャンセル")
        save_button = QPushButton("保存")
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


class StepsEditorDialog(QDialog):
    def __init__(self, run_id, records_csv, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"工程編集 - {run_id}")
        self.resize(900, 560)
        self.run_id = run_id
        self.records_csv = records_csv
        self.steps_by_run, self.fields, self.mtime = load_steps_table(records_csv)
        self.steps = [dict(step) for step in self.steps_by_run.get(run_id, [])]
        self.form_fields = list(STEP_FORM)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)

        title = QLabel(f"工程編集: {run_id}")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        root.addWidget(title)

        hint = QLabel(
            "この実験記録に紐づく工程を表で編集します。No は保存時に上から順番で自動採番されます。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #667085;")
        root.addWidget(hint)

        if not self.form_fields:
            empty = QLabel(
                "このパックには工程項目が定義されていません。工程を使うには、パック設定で工程項目を追加してください。"
            )
            empty.setWordWrap(True)
            empty.setStyleSheet(
                "color: #667085; padding: 16px; border: 1px solid #D0D7DE; "
                "border-radius: 8px; background: #F8FAFC;"
            )
            root.addWidget(empty, stretch=1)
            close_bar = QHBoxLayout()
            close_bar.addStretch()
            close_button = QPushButton("閉じる")
            close_button.clicked.connect(self.reject)
            close_bar.addWidget(close_button)
            root.addLayout(close_bar)
            return

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setWordWrap(False)
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
            QHeaderView::section {
                background: #EEF2F6;
                border: 1px solid #D0D7DE;
                padding: 6px;
                font-weight: 600;
            }
            """
        )
        self.table.itemSelectionChanged.connect(self.update_buttons)
        root.addWidget(self.table, stretch=1)

        button_row = QHBoxLayout()
        self.add_button = QPushButton("工程を追加")
        self.edit_button = QPushButton("選択した工程を編集")
        self.delete_button = QPushButton("選択した工程を削除")
        self.up_button = QPushButton("上へ")
        self.down_button = QPushButton("下へ")
        for button, slot in [
            (self.add_button, self.add_step),
            (self.edit_button, self.edit_step),
            (self.delete_button, self.delete_step),
            (self.up_button, lambda: self.move_step(-1)),
            (self.down_button, lambda: self.move_step(1)),
        ]:
            button.clicked.connect(slot)
            button_row.addWidget(button)
        button_row.addStretch()
        root.addLayout(button_row)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel_button = QPushButton("キャンセル")
        save_button = QPushButton("保存")
        save_button.setDefault(True)
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.save)
        footer.addWidget(cancel_button)
        footer.addWidget(save_button)
        root.addLayout(footer)

        self.refresh_table()

    def refresh_table(self, selected_row=None):
        columns = [("step_no", "No"), *self.form_fields]
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setRowCount(len(self.steps))
        self.table.setHorizontalHeaderLabels([label for _field, label in columns])

        for row_index, step in enumerate(self.steps):
            values = [str(row_index + 1)] + [
                step.get(field, "") for field, _label in self.form_fields
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, column_index, item)

        header = self.table.horizontalHeader()
        for column_index, (field, _label) in enumerate(columns):
            if field == "step_no":
                header.setSectionResizeMode(
                    column_index, QHeaderView.ResizeMode.ResizeToContents
                )
            elif field == "notes":
                header.setSectionResizeMode(
                    column_index, QHeaderView.ResizeMode.Stretch
                )
            else:
                header.setSectionResizeMode(
                    column_index, QHeaderView.ResizeMode.Interactive
                )
                self.table.setColumnWidth(column_index, 130)
        self.table.blockSignals(False)

        if self.steps:
            row_to_select = selected_row if selected_row is not None else 0
            row_to_select = max(0, min(row_to_select, len(self.steps) - 1))
            self.table.selectRow(row_to_select)
        self.update_buttons()

    def selected_index(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        index = selected[0].row()
        if not (0 <= index < len(self.steps)):
            return None
        return index

    def update_buttons(self):
        index = self.selected_index()
        has_selection = index is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        self.up_button.setEnabled(has_selection and index > 0)
        self.down_button.setEnabled(has_selection and index < len(self.steps) - 1)

    def add_step(self):
        dialog = StepEditDialog({}, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.steps.append(dialog.values())
        self.refresh_table(len(self.steps) - 1)

    def edit_step(self):
        index = self.selected_index()
        if index is None:
            QMessageBox.information(self, "工程を編集", "編集する工程を選択してください。")
            return
        dialog = StepEditDialog(dict(self.steps[index]), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.steps[index] = dialog.values()
        self.refresh_table(index)

    def delete_step(self):
        index = self.selected_index()
        if index is None:
            QMessageBox.information(self, "工程を削除", "削除する工程を選択してください。")
            return
        del self.steps[index]
        self.refresh_table(index)

    def move_step(self, offset):
        index = self.selected_index()
        if index is None:
            return
        target = index + offset
        if not (0 <= target < len(self.steps)):
            return
        self.steps[index], self.steps[target] = self.steps[target], self.steps[index]
        self.refresh_table(target)

    def save(self):
        saved_steps = []
        try:
            for index, step in enumerate(self.steps):
                updated = dict(step)
                updated["run_id"] = self.run_id
                updated["step_no"] = str(index + 1)
                validate_step_update(updated)
                saved_steps.append(updated)
            if saved_steps:
                self.steps_by_run[self.run_id] = saved_steps
            else:
                self.steps_by_run.pop(self.run_id, None)
            save_steps_table(
                self.records_csv,
                self.steps_by_run,
                self.fields,
                self.mtime,
            )
        except Exception as error:
            QMessageBox.critical(self, "保存エラー", str(error))
            return
        self.accept()


class StepEditDialog(QDialog):
    def __init__(self, step, parent=None):
        super().__init__(parent)
        self.setWindowTitle("工程を編集")
        self.resize(520, 420)
        self.step = step
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

        for field, label in STEP_FORM:
            widget = self.create_widget(field, step.get(field, ""))
            self.widgets[field] = widget
            form.addRow(label, widget)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel_button = QPushButton("キャンセル")
        save_button = QPushButton("保存")
        save_button.setDefault(True)
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)
        footer.addWidget(cancel_button)
        footer.addWidget(save_button)
        root.addLayout(footer)

    def create_widget(self, field, value):
        if field == "notes":
            widget = QTextEdit()
            widget.setPlainText(value)
            widget.setMinimumHeight(90)
            return widget
        if field == "action":
            widget = ScrollSafeComboBox()
            widget.setEditable(True)
            widget.addItems(["", *ACTION_CHOICES])
            widget.setCurrentText(value)
            return widget
        widget = QLineEdit()
        widget.setText(value)
        return widget

    def values(self):
        data = dict(self.step)
        for field, widget in self.widgets.items():
            if isinstance(widget, QTextEdit):
                value = widget.toPlainText()
            elif isinstance(widget, QComboBox):
                value = widget.currentText()
            else:
                value = widget.text()
            data[field] = value.strip()
        return data

    def accept(self):
        data = self.values()
        try:
            validate_step_update(data)
        except Exception as error:
            QMessageBox.critical(self, "入力エラー", str(error))
            return
        super().accept()


class RecordEditDialog(QDialog):
    def __init__(self, row, fields, parent=None, base_dir=None, title=None,
                 series_choices=None):
        super().__init__(parent)
        self.setWindowTitle(title or f"実験記録を編集: {row.get('run_id', '')}")
        self.resize(720, 620)
        self.row = row
        self.base_dir = base_dir
        self.series_choices = series_choices or []
        self.fields = [
            field for field in fields
            if field not in HIDDEN_EDIT_FIELDS
        ]
        self.widgets = {}

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_page = QWidget()
        form = QFormLayout()
        form_page.setLayout(form)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll.setWidget(form_page)
        root.addWidget(scroll, stretch=1)

        for field in self.fields:
            widget = self.create_widget(field, row.get(field, ""))
            self.widgets[field] = widget
            form.addRow(get_label(field), widget)

        button_bar = QWidget()
        button_bar.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(0, 8, 0, 0)
        button_layout.addStretch()
        cancel_button = QPushButton("キャンセル")
        save_button = QPushButton("保存")
        save_button.setDefault(True)
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)
        root.addWidget(button_bar)

    def create_widget(self, field, value):
        if field.endswith("_path"):
            return FilePathEditor(value, base_dir=self.base_dir, parent=self)
        if field in LONG_FIELDS:
            widget = QTextEdit()
            widget.setPlainText(value)
            widget.setMinimumHeight(80)
            return widget
        if field == "series_id" and self.series_choices:
            widget = ScrollSafeComboBox()
            widget.setEditable(True)
            widget.addItems(["", *self.series_choices])
            widget.setCurrentText(value)
            return widget
        if field in CHOICES:
            widget = ScrollSafeComboBox()
            widget.setEditable(True)
            widget.addItems(["", *CHOICES.get(field, [])])
            widget.setCurrentText(value)
            return widget
        widget = QLineEdit()
        widget.setText(value)
        return widget

    def values(self):
        data = dict(self.row)
        for field, widget in self.widgets.items():
            if isinstance(widget, QTextEdit):
                value = widget.toPlainText()
            elif isinstance(widget, FilePathEditor):
                value = widget.value()
            elif isinstance(widget, QComboBox):
                value = widget.currentText()
            else:
                value = widget.text()
            data[field] = value.strip()
        return data
