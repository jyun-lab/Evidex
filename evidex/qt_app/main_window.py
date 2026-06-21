import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import (
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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from evidex.core.fields import (
    CHOICES,
    FACETS,
    GCOL,
    STEP_FORM,
    feature_enabled,
)

from .detail import DetailMixin
from .filtering import FilterMixin
from .navigation import NavigationMixin
from .record_ops import RecordOpsMixin
from .table_view import TableMixin
from .theming import ThemeMixin
from .widgets import ElidingButton, ScrollSafeComboBox
from evidex.core.i18n import t


class EvidexQtWindow(
    QMainWindow,
    DetailMixin,
    NavigationMixin,
    FilterMixin,
    ThemeMixin,
    TableMixin,
    RecordOpsMixin,
):
    def __init__(self):
        super().__init__()
        from evidex.core import settings as app_settings
        self.dark = app_settings.get("theme") == "dark"
        self.setWindowTitle(t("qt.main.title"))
        self.resize(1100, 700)
        self.nav_view = None
        self._nav_open = {facet["field"]: False for facet in FACETS}
        self._nav_open["preset"] = False
        if FACETS:
            self._nav_open[FACETS[0]["field"]] = True
        self._detail_windows = []
        self.steps_enabled = feature_enabled("steps", bool(STEP_FORM))
        self.series_enabled = feature_enabled("series", False)

        self.statusBar().showMessage(t("qt.main.started"))

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
        self.title_label = QLabel(t("qt.main.title"))
        self.title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        self.note_label = QLabel(
            t("qt.main.preview_note")
        )
        self.note_label.setStyleSheet("color: #667085;")
        new_button = QPushButton(t("qt.run.add"))
        new_button.clicked.connect(self.add_new_record)
        self.series_manager_button = QPushButton(t("series.title.manager"))
        self.series_manager_button.clicked.connect(self.open_series_manager)
        reload_button = QPushButton(t("menu.file.reload"))
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
        self.nav_toggle_button.setToolTip(t("qt.main.toggle_navigation"))
        self.nav_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.nav_toggle_button.clicked.connect(self.toggle_nav)
        self.nav_toggle_button.setVisible(bool(FACETS))
        search_label = QLabel(t("btn.search"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            t("qt.main.search_placeholder")
        )
        self.search_input.textChanged.connect(self.apply_search)
        self.adv_toggle_button = QPushButton(t("btn.adv_filter", n="", arrow="▸"))
        self.adv_toggle_button.setStyleSheet(
            "QPushButton { border: none; color: #2563EB; font-weight: 600; }"
        )
        self.adv_toggle_button.clicked.connect(self.toggle_advanced_filters)
        clear_button = QPushButton(t("btn.clear"))
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
        self.preset_box.setPlaceholderText(t("qt.filter.preset_placeholder"))
        self.preset_box.currentTextChanged.connect(self._on_preset_selected)
        search_bar.addWidget(self.preset_box)

        self.preset_save_btn = QPushButton(t("btn.save"))
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
                lbl = _flbl(t("main.label.viscosity"))
                g0.addWidget(lbl, 0, c); c += 1
                self.filter_vmin = QLineEdit(); self.filter_vmin.setPlaceholderText("min")
                self.filter_vmin.textChanged.connect(self.apply_search)
                g0.addWidget(self.filter_vmin, 0, c); g0.setColumnStretch(c, 1); c += 1
                g0.addWidget(QLabel("〜"), 0, c); c += 1
                self.filter_vmax = QLineEdit(); self.filter_vmax.setPlaceholderText("max")
                self.filter_vmax.textChanged.connect(self.apply_search)
                g0.addWidget(self.filter_vmax, 0, c); g0.setColumnStretch(c, 1); c += 1
            if "date_range" in af:
                lbl = _flbl(t("pane.field.date"))
                g0.addWidget(lbl, 0, c); c += 1
                self.filter_dfrom = QLineEdit(); self.filter_dfrom.setPlaceholderText("from")
                self.filter_dfrom.textChanged.connect(self.apply_search)
                g0.addWidget(self.filter_dfrom, 0, c); g0.setColumnStretch(c, 1); c += 1
                g0.addWidget(QLabel("〜"), 0, c); c += 1
                self.filter_dto = QLineEdit(); self.filter_dto.setPlaceholderText("to")
                self.filter_dto.textChanged.connect(self.apply_search)
                g0.addWidget(self.filter_dto, 0, c); g0.setColumnStretch(c, 1); c += 1
            if "series" in af:
                lbl = _flbl(t("pane.field.series"))
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
            ("chip", t("qt.filter.chip_label")),
            ("experimenter", t("qt.filter.experimenter_label")),
            ("understanding", t("qt.filter.understanding_label")),
            ("action", t("qt.filter.action_label")),
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
            self.filter_has_raw = QCheckBox(t("main.label.has_raw"))
            self.filter_has_raw.stateChanged.connect(self.apply_search)
            flags_row.addWidget(self.filter_has_raw)
            if feature_enabled("steps"):
                self.filter_no_steps = QCheckBox(t("main.label.no_steps"))
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
                self.filter_unread = QCheckBox(t("main.label.unread_only"))
                self.filter_unread.stateChanged.connect(self.apply_search)
                g3.addWidget(self.filter_unread, 0, c); c += 1
            if "status" in af:
                lbl = _flbl(t("main.label.status_colon"))
                g3.addWidget(lbl, 0, c); c += 1
                self.filter_status_combo = ScrollSafeComboBox()
                self.filter_status_combo.setEditable(True)
                self.filter_status_combo.currentTextChanged.connect(self.apply_search)
                g3.addWidget(self.filter_status_combo, 0, c); g3.setColumnStretch(c, 1); c += 1
            if "liquid" in af:
                lbl = _flbl(t("main.label.liquid_colon"))
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
        self.detail_title = QLabel(t("qt.detail.select_record"))
        self.detail_title.setStyleSheet("font-weight: 700; color: #344054;")
        self.popout_button = ElidingButton(t("btn.open_in_window"))
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
        self.edit_button = ElidingButton(t("qt.run.edit"))
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self.edit_selected_record)
        self.steps_button = ElidingButton(t("main.menu.edit_steps"))
        self.steps_button.setEnabled(False)
        self.steps_button.clicked.connect(self.edit_selected_steps)
        self.delete_button = ElidingButton(t("qt.run.delete"))
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
        file_menu = menubar.addMenu(t("qt.menu.file"))
        file_menu.addAction(t("menu.file.open"), self._menu_open_file)
        file_menu.addAction(t("menu.file.reload"), self.reload_records)
        file_menu.addSeparator()
        file_menu.addAction(t("menu.file.settings"), self.open_settings)
        file_menu.addAction(t("menu.file.pack_manager"), self.open_schema_editor)
        file_menu.addSeparator()
        file_menu.addAction(t("menu.file.exit"), self.close)

        view_menu = menubar.addMenu(t("qt.menu.view"))
        self.nav_action = view_menu.addAction(t("qt.menu.navigation"))
        self.nav_action.setCheckable(True)
        self.nav_action.setChecked(bool(FACETS))
        self.nav_action.triggered.connect(self.toggle_nav)
        if not FACETS:
            self.nav_action.setVisible(False)

        self.dark_action = view_menu.addAction(t("menu.view.dark_mode"))
        self.dark_action.setCheckable(True)
        self.dark_action.setChecked(self.dark)
        self.dark_action.triggered.connect(self._menu_toggle_theme)

        if self.series_enabled:
            series_menu = menubar.addMenu(t("qt.menu.series"))
            series_menu.addAction(
                t("menu.series.manage"),
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

    def _get_columns(self):
        """現在の記録テーブルの列情報を返す"""
        if self.record_table is None:
            return []
        return self.record_table.columns

    def open_settings(self):
        """設定ダイアログを表示する"""
        from evidex.core import settings as app_settings
        from evidex.packs import get_pack_names

        dialog = QDialog(self)
        dialog.setWindowTitle(t("dialog.settings.title"))
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
        form.addRow(t("dialog.settings.pack"), pack_combo)

        theme_combo = QComboBox()
        theme_combo.addItems(["system", "light", "dark"])
        current_theme = app_settings.get("theme", "system")
        theme_combo.setCurrentText(current_theme)
        form.addRow(t("dialog.settings.theme"), theme_combo)

        lang_map = {"ja": t("schema_editor.str8"), "en": "English"}
        reverse_lang_map = {value: key for key, value in lang_map.items()}
        lang_combo = QComboBox()
        lang_combo.addItems(list(lang_map.values()))
        current_lang = app_settings.get("language", "en")
        lang_combo.setCurrentText(lang_map.get(current_lang, "English"))
        form.addRow(t("dialog.settings.language"), lang_combo)

        main_layout.addLayout(form)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_button = QPushButton(t("btn.cancel"))
        save_button = QPushButton(t("btn.save"))
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
                    t("dialog.settings.title"),
                    t("dialog.settings.msg_reboot"),
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
            t("qt.main.open_csv"),
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            from evidex.core import config
            config.RECORDS_CSV = Path(path)
            self.reload_records()

def run(argv=None):
    from evidex.core.csvio import extract_bundled_assets, ensure_initial_csv_files
    from evidex.core import config

    extract_bundled_assets()
    ensure_initial_csv_files(config.RECORDS_CSV.parent)

    app = QApplication(list(argv) if argv is not None else sys.argv)
    window = EvidexQtWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
