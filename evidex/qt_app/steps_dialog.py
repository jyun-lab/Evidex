"""Steps editor dialogs for the Qt app."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from evidex.core.fields import ACTION_CHOICES, STEP_FORM
from evidex.core.steps_table import (
    load_steps_table,
    save_steps_table,
    validate_step_update,
)

from .widgets import ScrollSafeComboBox


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
