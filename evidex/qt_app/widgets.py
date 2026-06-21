from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from evidex.core.attachments import join_paths, split_paths
from evidex.core.i18n import t


class FilePathEditor(QWidget):
    def __init__(self, initial_value="", base_dir=None, parent=None):
        super().__init__(parent)
        self.base_dir = base_dir
        self.paths = split_paths(initial_value)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self.list_widget = QTableWidget()
        self.list_widget.setColumnCount(3)
        self.list_widget.setHorizontalHeaderLabels([t("qt.files.name_column"), t("qt.files.path_column"), t("pane.field.status")])
        self.list_widget.verticalHeader().setVisible(False)
        self.list_widget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.list_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_widget.setMinimumHeight(96)
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.list_widget.itemSelectionChanged.connect(self.update_open_button)
        root.addWidget(self.list_widget)

        buttons = QHBoxLayout()
        add_button = QPushButton(t("qt.files.add"))
        remove_button = QPushButton(t("qt.files.remove_selected"))
        self.open_selected_button = QPushButton(t("qt.files.open_selected"))
        add_button.clicked.connect(self.add_files)
        remove_button.clicked.connect(self.remove_selected)
        self.open_selected_button.clicked.connect(self.open_selected_file)
        buttons.addWidget(add_button)
        buttons.addWidget(remove_button)
        buttons.addWidget(self.open_selected_button)
        buttons.addStretch()
        root.addLayout(buttons)
        self.refresh()

    def display_name(self, path):
        normalized = str(path).replace("\\", "/")
        return normalized.rsplit("/", 1)[-1] or normalized

    def resolved_path(self, path):
        source = Path(path)
        if source.is_absolute() or self.base_dir is None:
            return source
        return Path(self.base_dir) / source

    def refresh(self):
        self.list_widget.setRowCount(len(self.paths))
        for row_index, path in enumerate(self.paths):
            resolved = self.resolved_path(path)
            exists = resolved.exists()
            name_item = QTableWidgetItem(self.display_name(path))
            path_item = QTableWidgetItem(path)
            status_item = QTableWidgetItem(t("qt.file.exists") if exists else t("qt.file.missing"))
            name_item.setToolTip(path)
            path_item.setToolTip(str(resolved))
            status_item.setToolTip(str(resolved))
            if not exists:
                for item in (name_item, path_item, status_item):
                    item.setBackground(Qt.GlobalColor.yellow)
            self.list_widget.setItem(row_index, 0, name_item)
            self.list_widget.setItem(row_index, 1, path_item)
            self.list_widget.setItem(row_index, 2, status_item)
        header = self.list_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.list_widget.setColumnWidth(0, 180)
        self.adjust_table_height()
        self.update_open_button()

    def adjust_table_height(self):
        rows = max(1, min(4, len(self.paths) or 1))
        row_height = self.list_widget.verticalHeader().defaultSectionSize()
        header_height = self.list_widget.horizontalHeader().height()
        self.list_widget.setFixedHeight(header_height + row_height * rows + 8)

    def add_files(self):
        selected, _ = QFileDialog.getOpenFileNames(self, t("qt.files.add"))
        if not selected:
            return
        normalized = [self.normalize_path(path) for path in selected]
        self.paths = split_paths([*self.paths, *normalized])
        self.refresh()

    def normalize_path(self, path):
        if self.base_dir is None:
            return path
        try:
            relative = Path(path).resolve().relative_to(Path(self.base_dir).resolve())
            return relative.as_posix()
        except ValueError:
            return path

    def remove_selected(self):
        selected = self.list_widget.selectionModel().selectedRows()
        if not selected:
            return
        remove_indexes = {index.row() for index in selected}
        self.paths = [
            path for index, path in enumerate(self.paths)
            if index not in remove_indexes
        ]
        self.refresh()

    def selected_path(self):
        selected = self.list_widget.selectionModel().selectedRows()
        if not selected:
            return None
        index = selected[0].row()
        if not (0 <= index < len(self.paths)):
            return None
        return self.paths[index]

    def update_open_button(self):
        path = self.selected_path()
        self.open_selected_button.setEnabled(
            bool(path and self.resolved_path(path).exists())
        )

    def open_selected_file(self):
        path = self.selected_path()
        if not path:
            return
        resolved = self.resolved_path(path)
        if not resolved.exists():
            QMessageBox.warning(
                self,
                t("qt.file.not_found_title"),
                t("pane.msg.file_not_found", path=resolved),
            )
            self.update_open_button()
            return
        url = QUrl.fromLocalFile(str(resolved))
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                t("qt.file.open_failed_title"),
                t("qt.file.open_failed", path=resolved),
            )

    def value(self):
        return join_paths(self.paths)


class ScrollSafeComboBox(QComboBox):
    """フォーカスされていないときホイールイベントを無視し、親のスクロールに委ねる"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class ElidingButton(QPushButton):
    """幅が足りないとき '...' で省略表示する QPushButton"""

    def __init__(self, text="", parent=None):
        super().__init__("", parent)
        self._full_text = text
        self.setToolTip(text)
        self._update_elided()

    def setText(self, text):
        self._full_text = text
        self.setToolTip(text)
        self.updateGeometry()
        self._update_elided()

    def sizeHint(self):
        hint = super().sizeHint()
        text_width = self.fontMetrics().horizontalAdvance(self._full_text)
        return QSize(text_width + 24, hint.height())

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        return QSize(36, hint.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided()

    def _update_elided(self):
        font_metrics = self.fontMetrics()
        available = self.width() - 24
        elided = font_metrics.elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            max(available, 20),
        )
        super().setText(elided)
