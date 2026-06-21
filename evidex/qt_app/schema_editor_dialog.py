"""Schema editor dialog for the Qt app."""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .schema_adapter import SchemaAdapterMixin
from .schema_display import SchemaDisplayMixin
from .schema_fields import SchemaFieldsMixin
from .schema_packs import SchemaPacksMixin
from evidex.core.i18n import t


class SchemaEditorDialog(
    QDialog,
    SchemaFieldsMixin,
    SchemaAdapterMixin,
    SchemaDisplayMixin,
    SchemaPacksMixin,
):
    """パックの作成・編集・複製・削除を行うダイアログ。"""

    def __init__(self, parent):
        super().__init__(parent)
        from evidex.core import config, settings as app_settings

        self._config = config
        self._settings = app_settings
        self._schema = {}
        self._adapter = {}
        self._viz = {}
        self._builtin = True
        self._python_adapter = False
        self._adapter_headers = []
        self._channel_units_map = {}

        self.setWindowTitle(t("schema_editor.str1"))
        self.resize(960, 640)
        self.setMinimumSize(680, 480)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self._build_pack_list(main_layout)
        self._build_editor_panel(main_layout)
        self._connect_signals()
        self._refresh_pack_list()

    def _build_pack_list(self, layout):
        """左パネル: パック一覧と操作ボタン。"""
        left = QWidget()
        left.setFixedWidth(200)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel(t("schema_editor.str2")))

        self._pack_list = QListWidget()
        self._pack_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        left_layout.addWidget(self._pack_list, stretch=1)

        btn_row1 = QHBoxLayout()
        self._new_btn = QPushButton(t("schema_editor.str44"))
        self._dup_btn = QPushButton(t("schema_editor.str33"))
        self._del_btn = QPushButton(t("btn.delete"))
        btn_row1.addWidget(self._new_btn)
        btn_row1.addWidget(self._dup_btn)
        btn_row1.addWidget(self._del_btn)
        left_layout.addLayout(btn_row1)

        layout.addWidget(left)

    def _build_editor_panel(self, layout):
        """右パネル: タブ付きエディタ。"""
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel(t("schema_editor.pack_to_edit")))
        self._pack_name_label = QLabel("")
        self._pack_name_label.setStyleSheet("font-weight: bold;")
        top_row.addWidget(self._pack_name_label, stretch=1)
        self._active_label = QLabel("")
        self._active_label.setStyleSheet("color: #2563EB;")
        top_row.addWidget(self._active_label)
        right_layout.addLayout(top_row)

        self._tabs = QTabWidget()
        right_layout.addWidget(self._tabs, stretch=1)

        bottom_row = QHBoxLayout()
        self._readonly_label = QLabel("")
        self._readonly_label.setStyleSheet("color: #888;")
        bottom_row.addWidget(self._readonly_label, stretch=1)
        self._save_btn = QPushButton(t("btn.save"))
        self._save_btn.setEnabled(False)
        bottom_row.addWidget(self._save_btn)
        right_layout.addLayout(bottom_row)

        layout.addWidget(right, stretch=1)
        self._build_fields_tab()
        self._build_adapter_tab()
        self._build_display_tab()

    def _connect_signals(self):
        """各ウィジェットのシグナルを接続する。"""
        self._field_table.itemSelectionChanged.connect(
            self._on_field_select
        )
        self._apply_field_btn.clicked.connect(self._apply_field_edit)
        self._add_field_btn.clicked.connect(self._add_field)
        self._del_field_btn.clicked.connect(self._delete_field)
        self._up_field_btn.clicked.connect(
            lambda: self._move_field(-1)
        )
        self._down_field_btn.clicked.connect(
            lambda: self._move_field(1)
        )
        self._choose_csv_btn.clicked.connect(
            lambda: self._load_csv_columns(auto_detect=True)
        )
        self._reload_cols_btn.clicked.connect(
            lambda: self._load_csv_columns(
                self._csv_path_label.text() or None,
                auto_detect=False,
            )
        )
        self._x_column_combo.currentTextChanged.connect(
            self._on_x_column_changed
        )
        self._ch_select_all.clicked.connect(
            lambda: self._ch_toggle_all(True)
        )
        self._ch_clear_all.clicked.connect(
            lambda: self._ch_toggle_all(False)
        )
        self._ch_apply_unit.clicked.connect(self._apply_channel_unit)
        self._apply_adapter_btn.clicked.connect(
            self._apply_adapter_edit
        )
        self._test_adapter_btn.clicked.connect(self._test_parse)
        self._apply_display_btn.clicked.connect(
            self._apply_display_edit
        )
        self._pack_list.currentItemChanged.connect(
            lambda _current, _previous: self._on_pack_select()
        )
        self._save_btn.clicked.connect(self._save_current)
        self._new_btn.clicked.connect(self._create_pack)
        self._dup_btn.clicked.connect(self._duplicate_selected)
        self._del_btn.clicked.connect(self._delete_selected)


def open_schema_editor_dialog(parent):
    """パックの作成・編集・複製・削除を行うダイアログを表示する。"""
    dialog = SchemaEditorDialog(parent)
    dialog.exec()
