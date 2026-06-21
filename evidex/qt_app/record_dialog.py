"""Record edit dialog for the Qt app."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from evidex.core.fields import (
    CHOICES,
    HIDDEN_EDIT_FIELDS,
    LONG_FIELDS,
    get_label,
)

from .widgets import FilePathEditor, ScrollSafeComboBox


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
