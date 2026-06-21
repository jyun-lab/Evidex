import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from evidex.core.attachments import split_paths
from evidex.core.fields import (
    CHOICES,
    FACETS,
    GCOL,
    STEP_FORM,
    feature_enabled,
)
from evidex.core.i18n import t
from evidex.core.record_table import (
    default_new_record,
    load_record_table,
    resolve_record_file_path,
    row_values,
    save_record_rows,
    validate_record_update,
)
from evidex.core.series_table import load_series_table
from evidex.core.steps_table import load_steps_table

from .dialogs import (
    RecordEditDialog,
    SeriesManagerDialog,
    StepsEditorDialog,
)
from .detail import DetailMixin
from .filtering import FilterMixin
from .navigation import NavigationMixin
from .popout import DetailPopoutWindow
from .theme import _DARK, _LIGHT
from .widgets import ElidingButton, ScrollSafeComboBox


class EvidexQtWindow(QMainWindow, DetailMixin, NavigationMixin, FilterMixin):
    def __init__(self):
        super().__init__()
        from evidex.core import settings as app_settings
        self.dark = app_settings.get("theme") == "dark"
        self.setWindowTitle("Evidex Qt プレビュー")
        self.resize(1100, 700)
        self.nav_view = None
        self._nav_open = {facet["field"]: False for facet in FACETS}
        self._nav_open["preset"] = False
        if FACETS:
            self._nav_open[FACETS[0]["field"]] = True
        self._detail_windows = []
        self.steps_enabled = feature_enabled("steps", bool(STEP_FORM))
        self.series_enabled = feature_enabled("series", False)

        self.statusBar().showMessage("Qt版プレビューを起動しました。")

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 12, 14, 8)
        layout.setSpacing(8)

        self._build_header(layout)
        self._build_search_bar(layout)
        self._build_filter_panel(layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._build_nav_panel(splitter)
        self._build_table(splitter)
        self._build_detail_panel(splitter)

        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 2)
        layout.addWidget(splitter, stretch=1)
        self.splitter = splitter

        self.record_table = None
        self.filtered_rows = []
        self.current_row = None

        self._build_menubar()
        self._bind_shortcuts()

        self.setCentralWidget(root)
        self.steps_button.setVisible(self.steps_enabled)
        self.series_manager_button.setVisible(self.series_enabled)

        self._apply_theme()
        self.reload_records()
        self.apply_initial_splitter_sizes()
        QApplication.instance().processEvents()
        self.apply_initial_splitter_sizes()

    def _build_header(self, layout):
        header_widget = QWidget()
        header_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        header_widget.setLayout(header)
        self.title_label = QLabel("Evidex Qt プレビュー")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        self.note_label = QLabel(
            "Qt版の試作画面です。Tkinter版も引き続き使えます。"
        )
        self.note_label.setStyleSheet("color: #667085;")
        new_button = QPushButton("新しい実験記録を追加")
        new_button.clicked.connect(self.add_new_record)
        self.series_manager_button = QPushButton("シリーズ管理")
        self.series_manager_button.clicked.connect(self.open_series_manager)
        reload_button = QPushButton("再読み込み")
        reload_button.clicked.connect(self.reload_records)
        header.addWidget(self.title_label)
        header.addWidget(self.note_label, stretch=1)
        header.addWidget(new_button)
        header.addWidget(self.series_manager_button)
        header.addWidget(reload_button)
        layout.addWidget(header_widget)

    def _build_search_bar(self, layout):
        search_widget = QWidget()
        search_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        search_bar = QHBoxLayout()
        search_bar.setContentsMargins(0, 0, 0, 0)
        search_bar.setSpacing(8)
        search_widget.setLayout(search_bar)
        self.nav_toggle_button = QPushButton("☰")
        self.nav_toggle_button.setFixedSize(32, 28)
        self.nav_toggle_button.setToolTip("ナビゲーションの表示を切り替え")
        self.nav_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.nav_toggle_button.clicked.connect(self.toggle_nav)
        self.nav_toggle_button.setVisible(bool(FACETS))
        search_label = QLabel("検索")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "ID、日付、タイトル、要約、ファイルパスなどから検索"
        )
        self.search_input.textChanged.connect(self.apply_search)
        self.adv_toggle_button = QPushButton("詳細フィルタ ▸")
        self.adv_toggle_button.setStyleSheet(
            "QPushButton { border: none; color: #2563EB; font-weight: 600; }"
        )
        self.adv_toggle_button.clicked.connect(self.toggle_advanced_filters)
        clear_button = QPushButton("クリア")
        clear_button.clicked.connect(self.clear_all_filters)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #667085;")
        search_bar.addWidget(self.nav_toggle_button)
        search_bar.addWidget(search_label)
        search_bar.addWidget(self.search_input, stretch=1)
        search_bar.addWidget(self.adv_toggle_button)
        search_bar.addWidget(clear_button)
        self.preset_box = ScrollSafeComboBox()
        self.preset_box.setFixedWidth(140)
        self.preset_box.setPlaceholderText("プリセット")
        self.preset_box.currentTextChanged.connect(self._on_preset_selected)
        search_bar.addWidget(self.preset_box)

        self.preset_save_btn = QPushButton("保存")
        self.preset_save_btn.setFixedWidth(40)
        self.preset_save_btn.clicked.connect(self.save_preset)
        search_bar.addWidget(self.preset_save_btn)
        search_bar.addWidget(self.count_label)
        layout.addWidget(search_widget)

    def _build_filter_panel(self, layout):
        # ── 詳細フィルタパネル ──
        self.adv_panel = QWidget()
        self.adv_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.adv_panel.setVisible(False)
        self.adv_visible = False
        adv_outer = QVBoxLayout(self.adv_panel)
        adv_outer.setContentsMargins(0, 4, 0, 0)
        adv_outer.setSpacing(4)

        from evidex.core.fields import ADV_FILTERS
        af = set(ADV_FILTERS)
        self._filter_labels = []  # テーマ更新用の参照リスト
        _lbl_ss = "color: #667085; font-weight: 600;"

        def _flbl(text):
            """フィルタ用ラベルを作成し、テーマ更新用リストに追加"""
            lbl = QLabel(text)
            lbl.setStyleSheet(_lbl_ss)
            self._filter_labels.append(lbl)
            return lbl

        # ---- Row 0: 粘度範囲 / 日付範囲 / シリーズ ----
        self.filter_vmin = self.filter_vmax = None
        self.filter_dfrom = self.filter_dto = None
        self.filter_series = None
        if af & {"viscosity_range", "date_range", "series"}:
            g0 = QGridLayout(); g0.setHorizontalSpacing(8); g0.setVerticalSpacing(0)
            c = 0
            if "viscosity_range" in af:
                lbl = _flbl("粘度:")
                g0.addWidget(lbl, 0, c); c += 1
                self.filter_vmin = QLineEdit(); self.filter_vmin.setPlaceholderText("min")
                self.filter_vmin.textChanged.connect(self.apply_search)
                g0.addWidget(self.filter_vmin, 0, c); g0.setColumnStretch(c, 1); c += 1
                g0.addWidget(QLabel("〜"), 0, c); c += 1
                self.filter_vmax = QLineEdit(); self.filter_vmax.setPlaceholderText("max")
                self.filter_vmax.textChanged.connect(self.apply_search)
                g0.addWidget(self.filter_vmax, 0, c); g0.setColumnStretch(c, 1); c += 1
            if "date_range" in af:
                lbl = _flbl("日付:")
                g0.addWidget(lbl, 0, c); c += 1
                self.filter_dfrom = QLineEdit(); self.filter_dfrom.setPlaceholderText("from")
                self.filter_dfrom.textChanged.connect(self.apply_search)
                g0.addWidget(self.filter_dfrom, 0, c); g0.setColumnStretch(c, 1); c += 1
                g0.addWidget(QLabel("〜"), 0, c); c += 1
                self.filter_dto = QLineEdit(); self.filter_dto.setPlaceholderText("to")
                self.filter_dto.textChanged.connect(self.apply_search)
                g0.addWidget(self.filter_dto, 0, c); g0.setColumnStretch(c, 1); c += 1
            if "series" in af:
                lbl = _flbl("シリーズ:")
                g0.addWidget(lbl, 0, c); c += 1
                self.filter_series = ScrollSafeComboBox()
                self.filter_series.setEditable(True)
                self.filter_series.currentTextChanged.connect(self.apply_search)
                g0.addWidget(self.filter_series, 0, c); g0.setColumnStretch(c, 1); c += 1
            adv_outer.addLayout(g0)

        # ---- Row 1: チップ / 実験者 / 理解度 / 操作 ----
        self.filter_chip = None
        self.filter_who = None
        self.filter_understanding = None
        self.filter_action = None
        row1_items = [
            ("chip", "チップ:"),
            ("experimenter", "実験者:"),
            ("understanding", "理解度:"),
            ("action", "操作:"),
        ]
        row1_in_af = [(k, l) for k, l in row1_items if k in af]
        if row1_in_af:
            g1 = QGridLayout(); g1.setHorizontalSpacing(8); g1.setVerticalSpacing(0)
            c = 0
            for key, label in row1_in_af:
                lbl = _flbl(label)
                g1.addWidget(lbl, 0, c); c += 1
                if key == "chip":
                    self.filter_chip = QLineEdit()
                    self.filter_chip.textChanged.connect(self.apply_search)
                    g1.addWidget(self.filter_chip, 0, c); g1.setColumnStretch(c, 1); c += 1
                elif key == "experimenter":
                    self.filter_who = ScrollSafeComboBox(); self.filter_who.setEditable(True)
                    self.filter_who.currentTextChanged.connect(self.apply_search)
                    g1.addWidget(self.filter_who, 0, c); g1.setColumnStretch(c, 1); c += 1
                elif key == "understanding":
                    self.filter_understanding = ScrollSafeComboBox()
                    self.filter_understanding.addItem("")
                    for v in CHOICES.get("understanding", []):
                        self.filter_understanding.addItem(v)
                    self.filter_understanding.currentTextChanged.connect(self.apply_search)
                    g1.addWidget(self.filter_understanding, 0, c); g1.setColumnStretch(c, 1); c += 1
                elif key == "action":
                    self.filter_action = ScrollSafeComboBox(); self.filter_action.setEditable(True)
                    self.filter_action.currentTextChanged.connect(self.apply_search)
                    g1.addWidget(self.filter_action, 0, c); g1.setColumnStretch(c, 1); c += 1
            adv_outer.addLayout(g1)

        # ---- Row 2: フラグ (raw_pathあり / 工程なし) ----
        self.filter_has_raw = None
        self.filter_no_steps = None
        if "flags" in af:
            flags_row = QHBoxLayout(); flags_row.setSpacing(14)
            self.filter_has_raw = QCheckBox("raw_path あり")
            self.filter_has_raw.stateChanged.connect(self.apply_search)
            flags_row.addWidget(self.filter_has_raw)
            if feature_enabled("steps"):
                self.filter_no_steps = QCheckBox("工程なし")
                self.filter_no_steps.stateChanged.connect(self.apply_search)
                flags_row.addWidget(self.filter_no_steps)
            flags_row.addStretch()
            adv_outer.addLayout(flags_row)

        # ---- Row 3: Grade / 未読のみ / ステータス / 液体 ----
        self.grade_checks = {}
        self.filter_unread = None
        self.filter_status_combo = None
        self.filter_liquid = None
        row3_has = af & {"grades", "unread", "status", "liquid"}
        if row3_has:
            g3 = QGridLayout(); g3.setHorizontalSpacing(8); g3.setVerticalSpacing(0)
            c = 0
            if "grades" in af and feature_enabled("grading"):
                gl = _flbl("Grade:")
                g3.addWidget(gl, 0, c); c += 1
                for g in ("A", "B", "C"):
                    cb = QCheckBox(g)
                    cb.setStyleSheet(f"color: {GCOL.get(g, '#888')}; font-weight: 700;")
                    cb.stateChanged.connect(self.apply_search)
                    self.grade_checks[g] = cb
                    g3.addWidget(cb, 0, c); c += 1
            if "unread" in af:
                self.filter_unread = QCheckBox("未読のみ")
                self.filter_unread.stateChanged.connect(self.apply_search)
                g3.addWidget(self.filter_unread, 0, c); c += 1
            if "status" in af:
                lbl = _flbl("ステータス:")
                g3.addWidget(lbl, 0, c); c += 1
                self.filter_status_combo = ScrollSafeComboBox()
                self.filter_status_combo.setEditable(True)
                self.filter_status_combo.currentTextChanged.connect(self.apply_search)
                g3.addWidget(self.filter_status_combo, 0, c); g3.setColumnStretch(c, 1); c += 1
            if "liquid" in af:
                lbl = _flbl("液体:")
                g3.addWidget(lbl, 0, c); c += 1
                self.filter_liquid = ScrollSafeComboBox()
                self.filter_liquid.setEditable(True)
                self.filter_liquid.currentTextChanged.connect(self.apply_search)
                g3.addWidget(self.filter_liquid, 0, c); g3.setColumnStretch(c, 1); c += 1
            adv_outer.addLayout(g3)

        # フィルタ状態バー
        self.filter_status_bar = QLabel("")
        self.filter_status_bar.setStyleSheet(
            "color: #2563EB; font-size: 12px; padding: 2px 0;"
        )
        self.filter_status_bar.setVisible(False)
        adv_outer.addWidget(self.filter_status_bar)

        layout.addWidget(self.adv_panel)

    def _build_nav_panel(self, splitter):
        self.nav_panel = QWidget()
        self.nav_panel.setMinimumWidth(170)
        self.nav_panel.setMaximumWidth(240)
        self.nav_panel.setObjectName("navPanel")
        nav_outer = QVBoxLayout(self.nav_panel)
        nav_outer.setContentsMargins(0, 8, 0, 0)
        nav_outer.setSpacing(0)
        self.nav_scroll = QScrollArea()
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.nav_scroll.setStyleSheet("background: transparent;")
        self.nav_content = QWidget()
        self.nav_content.setStyleSheet("background: transparent;")
        self.nav_layout = QVBoxLayout(self.nav_content)
        self.nav_layout.setContentsMargins(6, 0, 6, 8)
        self.nav_layout.setSpacing(1)
        self.nav_scroll.setWidget(self.nav_content)
        nav_outer.addWidget(self.nav_scroll)
        self.nav_panel.setVisible(bool(FACETS))
        splitter.addWidget(self.nav_panel)

    def _build_table(self, splitter):
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.itemSelectionChanged.connect(self.show_selected_record)
        self.table.doubleClicked.connect(self._on_table_double_click)
        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.table.customContextMenuRequested.connect(
            self._show_context_menu
        )
        splitter.addWidget(self.table)

    def _build_detail_panel(self, splitter):
        self.detail_panel = QWidget()
        self.detail_panel.setMinimumWidth(200)
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(6)

        self.detail_action_bar = QWidget()
        self.detail_action_bar.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        action_layout = QHBoxLayout(self.detail_action_bar)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        self.detail_title = QLabel("記録を選択")
        self.detail_title.setStyleSheet("font-weight: 700; color: #344054;")
        self.popout_button = ElidingButton("別ウィンドウで開く")
        self.popout_button.setEnabled(False)
        self.popout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.popout_button.setStyleSheet("""
            QPushButton {
                border: none; color: #2563EB;
                font-weight: 600; font-size: 12px;
            }
            QPushButton:hover { color: #1D4ED8; text-decoration: underline; }
            QPushButton:disabled { color: #98A2B3; }
        """)
        self.popout_button.clicked.connect(self._open_selected_detail)
        self.edit_button = ElidingButton("実験記録を編集")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self.edit_selected_record)
        self.steps_button = ElidingButton("工程を編集")
        self.steps_button.setEnabled(False)
        self.steps_button.clicked.connect(self.edit_selected_steps)
        self.delete_button = ElidingButton("実験記録を削除")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected_record)
        self.delete_button.setStyleSheet(
            """
            QPushButton {
                color: #B42318;
                border-color: #FDA29B;
            }
            QPushButton:disabled {
                color: #98A2B3;
                border-color: #D0D5DD;
            }
            """
        )
        delete_separator = QFrame()
        delete_separator.setFrameShape(QFrame.Shape.VLine)
        delete_separator.setFrameShadow(QFrame.Shadow.Plain)
        delete_separator.setStyleSheet("color: #D0D7DE;")
        action_layout.addWidget(self.detail_title, stretch=1)
        action_layout.addWidget(self.popout_button)
        action_layout.addWidget(self.edit_button)
        action_layout.addWidget(self.steps_button)
        action_layout.addSpacing(8)
        action_layout.addWidget(delete_separator)
        action_layout.addSpacing(8)
        action_layout.addWidget(self.delete_button)

        self.detail_tabs = QTabWidget()
        self.detail_tabs.setUsesScrollButtons(True)
        self.detail_tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid #D0D7DE;
                background: #FFFFFF;
            }
            QTabBar::tab {
                padding: 7px 12px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                border: 1px solid #D0D7DE;
                border-bottom-color: #FFFFFF;
                font-weight: 600;
            }
            """
        )
        detail_layout.addWidget(self.detail_action_bar)
        detail_layout.addWidget(self.detail_tabs, stretch=1)
        splitter.addWidget(self.detail_panel)

    def _build_menubar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("ファイル(&F)")
        file_menu.addAction("開く...", self._menu_open_file)
        file_menu.addAction("再読み込み", self.reload_records)
        file_menu.addSeparator()
        file_menu.addAction("設定...", self.open_settings)
        file_menu.addAction("パック管理...", self.open_schema_editor)
        file_menu.addSeparator()
        file_menu.addAction("終了", self.close)

        view_menu = menubar.addMenu("表示(&V)")
        self.nav_action = view_menu.addAction("ナビゲーション")
        self.nav_action.setCheckable(True)
        self.nav_action.setChecked(bool(FACETS))
        self.nav_action.triggered.connect(self.toggle_nav)
        if not FACETS:
            self.nav_action.setVisible(False)

        self.dark_action = view_menu.addAction("ダークモード")
        self.dark_action.setCheckable(True)
        self.dark_action.setChecked(self.dark)
        self.dark_action.triggered.connect(self._menu_toggle_theme)

        if self.series_enabled:
            series_menu = menubar.addMenu("シリーズ(&S)")
            series_menu.addAction(
                "シリーズ管理...",
                self.open_series_manager,
            )

    def _bind_shortcuts(self):
        shortcut_specs = [
            ("Ctrl+N", self.add_new_record),
            ("Delete", self.delete_selected_record),
            ("F5", self.reload_records),
            ("Ctrl+F", self.search_input.setFocus),
            ("Down", lambda: self._nav_list(1)),
            ("Up", lambda: self._nav_list(-1)),
        ]
        self.shortcuts = []
        for key, callback in shortcut_specs:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    def apply_initial_splitter_sizes(self):
        nav_width = 190 if FACETS and self.nav_panel.isVisible() else 0
        self.splitter.setSizes([nav_width, 720, 340])

    def _theme(self):
        """現在のテーマカラー辞書を返す"""
        return _DARK if self.dark else _LIGHT

    def _get_columns(self):
        """現在の記録テーブルの列情報を返す"""
        if self.record_table is None:
            return []
        return self.record_table.columns

    def _apply_theme(self):
        """テーマに応じて主要ウィジェットのスタイルを更新する"""
        t = self._theme()

        # グローバルスタイル — 子ウィジェットにカスケードする
        self.setStyleSheet(f"""
            QMainWindow {{ background: {t['bg']}; color: {t['text']}; }}
            QDialog {{ background: {t['bg']}; color: {t['text']}; }}
            QLabel {{ color: {t['text']}; }}
            QLineEdit {{ background: {t['bg']}; color: {t['text']};
                         border: 1px solid {t['border']}; padding: 4px; }}
            QComboBox {{ background: {t['bg']}; color: {t['text']};
                         border: 1px solid {t['border']}; }}
            QComboBox QAbstractItemView {{ background: {t['bg']}; color: {t['text']}; }}
            QCheckBox {{ color: {t['text']}; }}
            QPushButton {{ background: {t['bg']}; color: {t['text']};
                           border: 1px solid {t['border']}; padding: 4px 12px;
                           border-radius: 4px; }}
            QPushButton:hover {{ background: {t['hover']}; }}
            QScrollArea {{ background: {t['bg']}; border: none; }}
            QScrollBar:vertical {{ background: {t['bg_alt']}; width: 8px; }}
            QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 4px; }}
            QScrollBar:horizontal {{ background: {t['bg_alt']}; height: 8px; }}
            QScrollBar::handle:horizontal {{ background: {t['border']}; border-radius: 4px; }}
            QMenuBar {{ background: {t['bg']}; color: {t['text']}; }}
            QMenuBar::item:selected {{ background: {t['hover']}; }}
            QMenu {{ background: {t['bg']}; color: {t['text']};
                     border: 1px solid {t['border']}; }}
            QMenu::item:selected {{ background: {t['selection']}; color: {t['selection_text']}; }}
            QSplitter::handle {{ background: {t['border_light']}; }}
        """)

        # テーブル
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {t['bg']};
                gridline-color: {t['border']};
                alternate-background-color: {t['bg_surface']};
                selection-background-color: {t['selection']};
                selection-color: {t['selection_text']};
                color: {t['text']};
            }}
            QTableWidget::item {{ padding: 5px; }}
            QTableWidget::item:selected {{
                background-color: {t['selection']};
                color: {t['selection_text']};
                border-top: 1px solid {t['selection_border']};
                border-bottom: 1px solid {t['selection_border']};
            }}
            QTableWidget::item:selected:!active {{
                background-color: {t['selection_inactive']};
                color: {t['selection_text']};
            }}
            QHeaderView::section {{
                background: {t['header_bg']};
                border: 1px solid {t['border']};
                padding: 6px; font-weight: 600;
                color: {t['text']};
            }}
        """)

        # ナビパネル
        if hasattr(self, "nav_panel"):
            self.nav_panel.setStyleSheet(f"""
                QWidget#navPanel {{
                    border-right: 1px solid {t['nav_border']};
                    background: {t['nav_bg']};
                }}
            """)

        # ☰ ボタン
        if hasattr(self, "nav_toggle_button"):
            self.nav_toggle_button.setStyleSheet(f"""
                QPushButton {{
                    border: 1px solid {t['border']}; border-radius: 5px;
                    background: {t['bg']}; color: {t['text']}; font-size: 14px;
                }}
                QPushButton:hover {{ background: {t['hover']}; }}
            """)

        # 詳細タブ
        if hasattr(self, "detail_tabs"):
            self.detail_tabs.setStyleSheet(f"""
                QTabWidget::pane {{
                    border: 1px solid {t['border']};
                    background: {t['bg']};
                }}
                QTabBar::tab {{
                    padding: 7px 12px; color: {t['text_muted']};
                    background: {t['bg_alt']};
                }}
                QTabBar::tab:selected {{
                    background: {t['bg']};
                    border: 1px solid {t['border']};
                    border-bottom-color: {t['bg']};
                    font-weight: 600; color: {t['text']};
                }}
            """)

        # 詳細パネルタイトル
        if hasattr(self, "detail_title"):
            self.detail_title.setStyleSheet(
                f"font-weight: 700; color: {t['text']};"
            )

        # フィルタ関連
        if hasattr(self, "filter_status_bar"):
            self.filter_status_bar.setStyleSheet(
                f"background: {t['bg_surface']}; padding: 4px 10px;"
                f" border-radius: 4px; color: {t['text_muted']};"
            )
        if hasattr(self, "count_label"):
            self.count_label.setStyleSheet(f"color: {t['text_muted']};")
        if hasattr(self, "preset_save_btn"):
            self.preset_save_btn.setStyleSheet(
                f"QPushButton {{ border: 1px solid {t['border']}; "
                f"border-radius: 3px; padding: 2px 6px; "
                f"background: {t['bg_surface']}; color: {t['text']}; }}"
                f"QPushButton:hover {{ background: {t['hover']}; }}"
            )
        if hasattr(self, "adv_toggle_button"):
            self.adv_toggle_button.setStyleSheet(
                f"QPushButton {{ border: none; color: {t['link']}; font-weight: 600; }}"
            )

        # ポップアウトボタン
        if hasattr(self, "popout_button"):
            self.popout_button.setStyleSheet(f"""
                QPushButton {{
                    border: none; color: {t['link']};
                    font-weight: 600; font-size: 12px; background: transparent;
                }}
                QPushButton:hover {{ color: {t['selection_border']}; text-decoration: underline; }}
                QPushButton:disabled {{ color: {t['text_muted']}; }}
            """)

        # 削除ボタン（赤は維持）
        if hasattr(self, "delete_button"):
            self.delete_button.setStyleSheet(f"""
                QPushButton {{
                    color: #B42318; border-color: #FDA29B;
                    background: {t['bg']};
                }}
                QPushButton:hover {{ background: {t['hover']}; }}
                QPushButton:disabled {{ color: #98A2B3; border-color: #D0D5DD; }}
            """)

        # ヘッダーラベル
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(
                f"font-size: 20px; font-weight: 700; color: {t['text']};"
            )
        if hasattr(self, "note_label"):
            self.note_label.setStyleSheet(f"color: {t['text_muted']};")

        # フィルタラベル
        for lbl in getattr(self, "_filter_labels", []):
            lbl.setStyleSheet(f"color: {t['text_muted']}; font-weight: 600;")

        # ナビパネル再描画
        if self.record_table is not None:
            self.build_nav()
        self._apply_grade_row_colors()
        self.show_selected_record()

    def _apply_grade_row_colors(self):
        """テーブル行にGradeベースの背景色を適用する"""
        grade_colors = self._theme()["grade_row"]
        grade_col = None
        for column_index, column in enumerate(self._get_columns()):
            if column.key == "grade":
                grade_col = column_index
                break
        if grade_col is None:
            return
        for row_index in range(self.table.rowCount()):
            item = self.table.item(row_index, grade_col)
            if item is None:
                continue
            grade = item.text().strip().upper()
            if grade in grade_colors:
                background = QColor(grade_colors[grade])
                for column_index in range(self.table.columnCount()):
                    cell = self.table.item(row_index, column_index)
                    if cell is not None:
                        cell.setBackground(background)

    def _card_qss(self, name="card"):
        """カード型QFrameのテーマ対応スタイル"""
        t = self._theme()
        return f"""QFrame#{name} {{
            border: 1px solid {t['border']};
            border-radius: 8px; background: {t['bg']};
        }}"""

    def _muted_ss(self):
        return f"color: {self._theme()['text_muted']};"

    def _muted_bold_ss(self):
        return f"color: {self._theme()['text_muted']}; font-weight: 600;"

    def toggle_theme(self):
        """ダーク/ライトテーマを切り替える"""
        self.dark = not self.dark
        self._apply_theme()

    def _menu_toggle_theme(self):
        self.toggle_theme()
        if hasattr(self, "dark_action"):
            self.dark_action.setChecked(self.dark)
        from evidex.core import settings as app_settings
        app_settings.set("theme", "dark" if self.dark else "light")

    def open_settings(self):
        """設定ダイアログを表示する"""
        from evidex.core import settings as app_settings
        from evidex.packs import get_pack_names

        dialog = QDialog(self)
        dialog.setWindowTitle("設定")
        dialog.setMinimumWidth(360)
        dialog.setModal(True)

        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        pack_combo = QComboBox()
        pack_names = list(get_pack_names())
        pack_combo.addItems(pack_names)
        current_pack = app_settings.get("active_pack")
        if current_pack in pack_names:
            pack_combo.setCurrentText(current_pack)
        form.addRow("アクティブなパック:", pack_combo)

        theme_combo = QComboBox()
        theme_combo.addItems(["system", "light", "dark"])
        current_theme = app_settings.get("theme", "system")
        theme_combo.setCurrentText(current_theme)
        form.addRow("テーマ:", theme_combo)

        lang_map = {"ja": "日本語", "en": "English"}
        reverse_lang_map = {value: key for key, value in lang_map.items()}
        lang_combo = QComboBox()
        lang_combo.addItems(list(lang_map.values()))
        current_lang = app_settings.get("language", "en")
        lang_combo.setCurrentText(lang_map.get(current_lang, "English"))
        form.addRow("言語 / Language:", lang_combo)

        main_layout.addLayout(form)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_button = QPushButton("キャンセル")
        save_button = QPushButton("保存")
        save_button.setDefault(True)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)
        main_layout.addLayout(button_layout)

        def save():
            old_pack = app_settings.get("active_pack")
            new_pack = pack_combo.currentText()
            old_lang = app_settings.get("language", "en")
            new_lang = reverse_lang_map.get(
                lang_combo.currentText(),
                "en",
            )
            new_theme = theme_combo.currentText()

            app_settings.set("active_pack", new_pack)
            app_settings.set("theme", new_theme)
            app_settings.set("language", new_lang)

            target_dark = new_theme == "dark"
            if target_dark != self.dark:
                self.dark = target_dark
                self._apply_theme()
                if hasattr(self, "dark_action"):
                    self.dark_action.setChecked(self.dark)

            if old_pack != new_pack or old_lang != new_lang:
                QMessageBox.information(
                    dialog,
                    "設定",
                    "アクティブパックや言語の変更は、"
                    "次回アプリ起動時に反映されます。",
                )
            dialog.accept()

        save_button.clicked.connect(save)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec()

    def open_schema_editor(self):
        from .schema_editor_dialog import open_schema_editor_dialog

        open_schema_editor_dialog(self)

    def _menu_open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "CSVファイルを開く",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            from evidex.core import config
            config.RECORDS_CSV = Path(path)
            self.reload_records()

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

    def select_run_id(self, run_id):
        if not run_id:
            return
        for row_index, row in enumerate(self.filtered_rows):
            if row.get("run_id", "") == run_id:
                self.table.selectRow(row_index)
                self.show_selected_record()
                return


def run(argv=None):
    app = QApplication(list(argv) if argv is not None else sys.argv)
    window = EvidexQtWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
