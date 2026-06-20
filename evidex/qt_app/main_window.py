import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QKeySequence,
    QPixmap,
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
    QInputDialog,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from evidex.core.attachments import split_paths
from evidex.core.fields import (
    ACTION_CHOICES,
    CHOICES,
    FACETS,
    GCOL,
    LONG_FIELDS,
    STEP_FORM,
    feature_enabled,
    get_label,
)
from evidex.core.filtering import fnum, norm, row_matches
from evidex.core.icons import icon_for_action
from evidex.core.i18n import t
from evidex.core.media import is_image_path
from evidex.core.record_table import (
    default_new_record,
    load_record_table,
    record_basic_items,
    record_file_entries,
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
from .popout import DetailPopoutWindow
from .theme import _DARK, _LIGHT
from .waveform import RawDataPreviewWidget
from .widgets import ElidingButton, ScrollSafeComboBox


class EvidexQtWindow(QMainWindow):
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

        splitter = QSplitter(Qt.Orientation.Horizontal)

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

        splitter.addWidget(self.nav_panel)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail_panel)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 2)
        layout.addWidget(splitter, stretch=1)

        self.splitter = splitter

        self.record_table = None
        self.filtered_rows = []
        self.current_row = None

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

        self.setCentralWidget(root)
        self.steps_button.setVisible(self.steps_enabled)
        self.series_manager_button.setVisible(self.series_enabled)

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

        self._apply_theme()
        self.reload_records()
        self.apply_initial_splitter_sizes()
        QApplication.instance().processEvents()
        self.apply_initial_splitter_sizes()

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

    def _prefs_path(self):
        from evidex.core import config
        return config.RECORDS_CSV.parent / "evidex_prefs.json"

    def _load_prefs(self):
        try:
            return json.loads(
                self._prefs_path().read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_prefs(self, prefs):
        try:
            self._prefs_path().write_text(
                json.dumps(prefs, ensure_ascii=False, indent=1),
                encoding="utf-8")
            return True
        except Exception as e:
            QMessageBox.warning(self, "保存エラー", str(e))
            return False

    def _on_preset_selected(self, name):
        if not name:
            return
        st = self._load_prefs().get("presets", {}).get(name)
        if st:
            self._apply_filter_state(st)

    def save_preset(self):
        name, ok = QInputDialog.getText(
            self, "プリセット保存", "プリセット名を入力:")
        if not ok or not name.strip():
            return
        name = name.strip()
        prefs = self._load_prefs()
        prefs.setdefault("presets", {})[name] = self._filter_state()
        if self._save_prefs(prefs):
            self._refresh_presets()
            self.preset_box.setCurrentText(name)

    def _refresh_presets(self):
        self.preset_box.blockSignals(True)
        current = self.preset_box.currentText()
        self.preset_box.clear()
        self.preset_box.addItem("")
        names = sorted(self._load_prefs().get("presets", {}))
        for n in names:
            self.preset_box.addItem(n)
        self.preset_box.setCurrentText(current)
        self.preset_box.blockSignals(False)

    def _clear_nav_layout(self):
        while self.nav_layout.count():
            item = self.nav_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _facet_matches(self, row, facet, value):
        row_value = str(row.get(facet["field"], "") or "")
        match_type = facet["match"]
        if match_type == "norm":
            return norm(row_value) == norm(value)
        if match_type == "strip":
            return row_value.strip() == value
        if match_type == "upper":
            return row_value.strip().upper() == value
        return row_value == value

    def _facet_items(self, facet):
        field = facet["field"]
        rows = self.record_table.rows
        if facet["source"] == "choices":
            values = [str(value) for value in CHOICES.get(field, []) if value]
        else:
            values = sorted(
                {
                    str(row.get(field, "") or "")
                    for row in rows
                    if str(row.get(field, "") or "").strip()
                }
            )
        items = []
        for value in values:
            count = sum(
                1 for row in rows if self._facet_matches(row, facet, value)
            )
            if facet["source"] != "choices" or count > 0:
                items.append((value, count))
        return items

    _NAV_ITEM_SS = """
        QPushButton {{
            border: none; border-radius: 5px;
            background: {bg};
            color: {fg};
            text-align: left;
            padding: 5px 8px;
            font-size: 12px;
        }}
        QPushButton:hover {{ background: {hover}; }}
    """

    def _add_nav_item(self, label_text, view, count):
        selected = self.nav_view == view
        theme = self._theme()
        if selected:
            bg = "#E8F0FE" if not self.dark else "#1A3A5C"
            fg = "#1967D2" if not self.dark else "#7CB3F2"
            hover = bg
        else:
            bg = theme["bg"]
            fg = theme["text"]
            hover = theme["hover"]
        btn = QPushButton(f"{label_text}  ")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(self._NAV_ITEM_SS.format(bg=bg, fg=fg, hover=hover))
        # 件数バッジを右寄せするためレイアウトを使う
        inner = QHBoxLayout(btn)
        inner.setContentsMargins(8, 4, 8, 4)
        inner.setSpacing(0)
        inner.addStretch()
        badge = QLabel(str(count))
        badge.setStyleSheet(
            f"color: {fg if selected else theme['text_muted']};"
            "background: transparent; font-size: 11px;"
        )
        inner.addWidget(badge)
        btn.clicked.connect(
            lambda _=False, v=view: self._set_nav_view(v)
        )
        if isinstance(view, tuple) and len(view) == 2 and view[0] == "preset":
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, n=view[1], b=btn: self._preset_context_menu(pos, n, b)
            )
        self.nav_layout.addWidget(btn)

    def _preset_context_menu(self, pos, preset_name, btn):
        menu = QMenu(self)
        delete_action = menu.addAction("削除")
        chosen = menu.exec(btn.mapToGlobal(pos))
        if chosen == delete_action:
            prefs = self._load_prefs()
            prefs.get("presets", {}).pop(preset_name, None)
            self._save_prefs(prefs)
            self._refresh_presets()
            if self.nav_view == ("preset", preset_name):
                self.nav_view = None
            self.build_nav()
            self.apply_search()

    def _add_nav_section_header(self, title, field):
        opened = self._nav_open.get(field, False)
        arrow = "▾" if opened else "▸"  # ▾ / ▸
        hdr = QPushButton(f" {arrow}  {title}")
        hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        theme = self._theme()
        hdr.setStyleSheet(f"""
            QPushButton {{
                text-align: left; border: none; padding: 4px 6px;
                font-size: 11px; font-weight: 700;
                color: {theme['text_muted']}; background: transparent;
            }}
            QPushButton:hover {{ background: {theme['hover']}; }}
        """)
        hdr.clicked.connect(
            lambda _=False, k=field: self._toggle_nav_section(k)
        )
        self.nav_layout.addWidget(hdr)

    def _add_nav_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(
            f"color: {self._theme()['border_light']}; margin: 4px 8px;"
        )
        line.setFixedHeight(1)
        self.nav_layout.addWidget(line)

    def _set_nav_view(self, view):
        self.nav_view = view
        self.apply_search()
        self.build_nav()

    def _toggle_nav_section(self, field):
        self._nav_open[field] = not self._nav_open.get(field, False)
        self.build_nav()

    def build_nav(self):
        if not FACETS or self.record_table is None:
            self.nav_panel.setVisible(False)
            self.nav_toggle_button.setVisible(False)
            return

        self.nav_toggle_button.setVisible(True)
        self._clear_nav_layout()

        # 「すべて」
        self._add_nav_item("すべて", None, len(self.record_table.rows))

        for facet in FACETS:
            items = self._facet_items(facet)
            if not items:
                continue
            field = facet["field"]
            self._add_nav_separator()
            label_key = facet.get("label_key", "")
            title = t(label_key) if label_key else get_label(field)
            self._add_nav_section_header(title, field)
            if self._nav_open.get(field, False):
                for value, count in items:
                    self._add_nav_item(value, (field, value), count)

        # ── 保存した検索（プリセット）──
        prefs = self._load_prefs().get("presets", {})
        if prefs:
            p_items = []
            for p_name in sorted(prefs.keys()):
                f_p = self._preset_to_filters(prefs[p_name])
                cnt = sum(1 for r in self.record_table.rows
                          if row_matches(r, f_p, self.steps_by_run))
                p_items.append((p_name, cnt))
            self._add_nav_separator()
            self._add_nav_section_header("保存した検索", "preset")
            if self._nav_open.get("preset", False):
                for p_name, cnt in p_items:
                    self._add_nav_item(p_name, ("preset", p_name), cnt)
        self.nav_layout.addStretch()

    def _in_nav_view(self, row, view):
        if view is None:
            return True
        kind, value = view
        if kind == "preset":
            st = self._load_prefs().get("presets", {}).get(value)
            if not st:
                return True
            f = self._preset_to_filters(st)
            return row_matches(row, f, self.steps_by_run)
        facet = next((item for item in FACETS if item["field"] == kind), None)
        if facet is None:
            return True
        row_value = str(row.get(kind, "") or "")
        match_type = facet["match"]
        if match_type == "norm":
            return norm(row_value) == norm(value)
        if match_type == "strip":
            return row_value.strip() == value
        if match_type == "upper":
            return row_value.strip().upper() == value
        return row_value == value

    def toggle_nav(self):
        if not FACETS:
            return
        visible = not self.nav_panel.isVisible()
        self.nav_panel.setVisible(visible)
        if visible:
            sizes = self.splitter.sizes()
            table_width = sizes[1] if len(sizes) > 1 else 720
            detail_width = sizes[2] if len(sizes) > 2 else 340
            self.splitter.setSizes([190, table_width, detail_width])
        if hasattr(self, "nav_action"):
            self.nav_action.setChecked(visible)

    def _nav_list(self, delta):
        """↑↓キーでテーブルの選択行を移動。入力欄にフォーカス中は奪わない。"""
        focused = QApplication.focusWidget()
        if isinstance(focused, (QLineEdit, QComboBox, QTextEdit)):
            return
        current = self.table.currentRow()
        new_row = current + delta
        if 0 <= new_row < self.table.rowCount():
            self.table.selectRow(new_row)
            self.show_selected_record()

    def _refresh_filter_choices(self):
        """フィルタコンボの選択肢をデータから更新"""
        rows = self.record_table.rows

        def update_combo(combo, values):
            if combo is None:
                return
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("")
            for v in sorted(set(values)):
                if v:
                    combo.addItem(v)
            combo.setCurrentText(current)
            combo.blockSignals(False)

        update_combo(
            self.filter_series,
            [(r.get("series_id", "") or "").strip() for r in rows],
        )
        update_combo(
            self.filter_status_combo,
            [(r.get("status", "") or "").strip() for r in rows],
        )
        update_combo(
            self.filter_who,
            [(r.get("experimenter", "") or "").strip() for r in rows],
        )
        update_combo(
            self.filter_liquid,
            [(r.get("liquid", "") or "").strip() for r in rows],
        )
        if self.filter_action is not None:
            action_values = list(ACTION_CHOICES)
            for steps in self.steps_by_run.values():
                for s in steps:
                    a = (s.get("action", "") or "").strip()
                    if a:
                        action_values.append(a)
            update_combo(self.filter_action, action_values)

    def _build_filter_dict(self):
        """UI状態からrow_matchesに渡すフィルタ辞書を構築"""
        def _combo_text(w):
            return w.currentText().strip() if w is not None else ""
        def _line_text(w):
            return w.text().strip() if w is not None else ""
        def _check(w):
            return w.isChecked() if w is not None else False
        def _fnum(s):
            try:
                return float(s) if s else None
            except ValueError:
                return None
        f = {
            "text": self.search_input.text().strip(),
            "grades": [g for g, cb in self.grade_checks.items() if cb.isChecked()],
            "status": _combo_text(self.filter_status_combo),
            "liquid": _combo_text(self.filter_liquid),
            "vmin": _fnum(_line_text(self.filter_vmin)),
            "vmax": _fnum(_line_text(self.filter_vmax)),
            "chip": _line_text(self.filter_chip),
            "who": _combo_text(self.filter_who),
            "unread": _check(self.filter_unread),
            "dfrom": _line_text(self.filter_dfrom),
            "dto": _line_text(self.filter_dto),
            "series": _combo_text(self.filter_series),
            "understanding": _combo_text(self.filter_understanding),
            "action": _combo_text(self.filter_action),
            "has_raw": _check(self.filter_has_raw),
            "no_steps": _check(self.filter_no_steps),
        }
        return f

    def _filter_state(self):
        """プリセット保存用: 現在のフィルタUI状態を辞書で返す（文字列のまま）"""
        def _combo_text(w):
            return w.currentText().strip() if w is not None else ""
        def _line_text(w):
            return w.text().strip() if w is not None else ""
        def _check(w):
            return w.isChecked() if w is not None else False
        return {
            "text": self.search_input.text().strip(),
            "grades": {g: cb.isChecked() for g, cb in self.grade_checks.items()},
            "status": _combo_text(self.filter_status_combo),
            "liquid": _combo_text(self.filter_liquid),
            "vmin": _line_text(self.filter_vmin),
            "vmax": _line_text(self.filter_vmax),
            "chip": _line_text(self.filter_chip),
            "who": _combo_text(self.filter_who),
            "unread": _check(self.filter_unread),
            "dfrom": _line_text(self.filter_dfrom),
            "dto": _line_text(self.filter_dto),
            "series": _combo_text(self.filter_series),
            "understanding": _combo_text(self.filter_understanding),
            "action": _combo_text(self.filter_action),
            "has_raw": _check(self.filter_has_raw),
            "no_steps": _check(self.filter_no_steps),
        }

    def _apply_filter_state(self, st):
        """プリセットからフィルタUIを復元"""
        self.search_input.blockSignals(True)
        self.search_input.setText(st.get("text", ""))
        self.search_input.blockSignals(False)
        for w, key in ((self.filter_vmin, "vmin"), (self.filter_vmax, "vmax"),
                       (self.filter_chip, "chip"),
                       (self.filter_dfrom, "dfrom"), (self.filter_dto, "dto")):
            if w is not None:
                w.blockSignals(True)
                w.setText(st.get(key, ""))
                w.blockSignals(False)
        for w, key in ((self.filter_status_combo, "status"),
                       (self.filter_liquid, "liquid"),
                       (self.filter_who, "who"),
                       (self.filter_series, "series"),
                       (self.filter_understanding, "understanding"),
                       (self.filter_action, "action")):
            if w is not None:
                w.blockSignals(True)
                w.setCurrentText(st.get(key, ""))
                w.blockSignals(False)
        grades = st.get("grades", {})
        for g, cb in self.grade_checks.items():
            cb.blockSignals(True)
            cb.setChecked(bool(grades.get(g, False)))
            cb.blockSignals(False)
        for w, key in ((self.filter_unread, "unread"),
                       (self.filter_has_raw, "has_raw"),
                       (self.filter_no_steps, "no_steps")):
            if w is not None:
                w.blockSignals(True)
                w.setChecked(bool(st.get(key, False)))
                w.blockSignals(False)
        self.apply_search()

    def _preset_to_filters(self, st):
        """保存プリセット辞書 → row_matches用フィルタ辞書"""
        return {
            "text": st.get("text", "").strip(),
            "vmin": fnum(st.get("vmin", "")),
            "vmax": fnum(st.get("vmax", "")),
            "grades": [g for g, v in st.get("grades", {}).items() if v],
            "chip": st.get("chip", "").strip(),
            "status": st.get("status", "").strip(),
            "who": st.get("who", "").strip(),
            "liquid": st.get("liquid", "").strip(),
            "unread": bool(st.get("unread", False)),
            "dfrom": st.get("dfrom", "").strip(),
            "dto": st.get("dto", "").strip(),
            "series": st.get("series", "").strip(),
            "understanding": st.get("understanding", "").strip(),
            "action": st.get("action", "").strip(),
            "has_raw": bool(st.get("has_raw", False)),
            "no_steps": bool(st.get("no_steps", False)),
        }

    def _adv_filter_count(self):
        """有効な詳細フィルタ条件の数"""
        f = self._build_filter_dict()
        n = 0
        if f["grades"]:
            n += 1
        if f["dfrom"]:
            n += 1
        if f["dto"]:
            n += 1
        if f["vmin"] is not None:
            n += 1
        if f["vmax"] is not None:
            n += 1
        for k in ("series", "status", "who", "action", "chip",
                   "liquid", "understanding"):
            if f.get(k):
                n += 1
        for k in ("has_raw", "no_steps", "unread"):
            if f.get(k):
                n += 1
        return n

    def apply_search(self):
        if self.record_table is None:
            return
        f = self._build_filter_dict()
        base = self.record_table.rows
        if self.nav_view is not None:
            base = [
                row for row in base
                if self._in_nav_view(row, self.nav_view)
            ]
        self.filtered_rows = [
            r for r in base
            if row_matches(r, f, self.steps_by_run)
        ]
        self.populate_table()
        # フィルタ状態の更新
        n = self._adv_filter_count()
        arrow = "▾" if self.adv_visible else "▸"
        suffix = f" ({n})" if n else ""
        self.adv_toggle_button.setText(f"詳細フィルタ{suffix} {arrow}")
        # 状態バー
        parts = []
        if f["grades"]:
            parts.append(f"Grade: {','.join(f['grades'])}")
        if f["vmin"] is not None or f["vmax"] is not None:
            lo = f["vmin"] if f["vmin"] is not None else "..."
            hi = f["vmax"] if f["vmax"] is not None else "..."
            parts.append(f"粘度: {lo}〜{hi}")
        if f["dfrom"] or f["dto"]:
            parts.append(f"日付: {f['dfrom'] or '...'} 〜 {f['dto'] or '...'}")
        for key, label in (("series", "シリーズ"), ("chip", "チップ"),
                           ("status", "ステータス"), ("who", "実験者"),
                           ("understanding", "理解度"), ("action", "操作"),
                           ("liquid", "液体")):
            if f.get(key):
                parts.append(f"{label}: {f[key]}")
        if f["has_raw"]:
            parts.append("raw_pathあり")
        if f["no_steps"]:
            parts.append("工程なし")
        if f["unread"]:
            parts.append("未読のみ")
        if parts:
            self.filter_status_bar.setText("フィルタ: " + " | ".join(parts))
            self.filter_status_bar.setVisible(True)
        else:
            self.filter_status_bar.setVisible(False)
        self.build_nav()

    def toggle_advanced_filters(self):
        self.adv_visible = not self.adv_visible
        self.adv_panel.setVisible(self.adv_visible)
        n = self._adv_filter_count()
        arrow = "▾" if self.adv_visible else "▸"
        suffix = f" ({n})" if n else ""
        self.adv_toggle_button.setText(f"詳細フィルタ{suffix} {arrow}")

    def clear_all_filters(self):
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        for cb in self.grade_checks.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        for w in (self.filter_vmin, self.filter_vmax,
                  self.filter_dfrom, self.filter_dto, self.filter_chip):
            if w is not None:
                w.blockSignals(True)
                w.clear()
                w.blockSignals(False)
        for combo in (self.filter_series, self.filter_status_combo,
                      self.filter_who, self.filter_action,
                      self.filter_understanding, self.filter_liquid):
            if combo is not None:
                combo.blockSignals(True)
                combo.setCurrentText("")
                combo.blockSignals(False)
        for flag in (self.filter_has_raw, self.filter_no_steps,
                     self.filter_unread):
            if flag is not None:
                flag.blockSignals(True)
                flag.setChecked(False)
                flag.blockSignals(False)
        self.apply_search()

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

    def show_selected_record(self):
        selected = self.table.selectedItems()
        if not selected:
            self.show_empty_detail()
            return
        row_index = selected[0].row()
        first_item = self.table.item(row_index, 0)
        source_index = first_item.data(Qt.ItemDataRole.UserRole) if first_item else None
        if source_index is None:
            return
        try:
            row = self.record_table.rows[int(source_index)]
        except (TypeError, ValueError, IndexError):
            return
        self.current_row = row
        self.edit_button.setEnabled(True)
        self.steps_button.setEnabled(self.steps_enabled)
        self.delete_button.setEnabled(True)
        self.popout_button.setEnabled(True)
        self.detail_title.setText(row.get("run_id", "") or "No ID")
        self.render_detail(row)

    def show_empty_detail(self):
        self.detail_tabs.clear()
        self.detail_tabs.addTab(
            self.empty_tab("左の表から実験記録を選択してください。"),
            "基本情報",
        )
        self.detail_tabs.addTab(
            self.empty_tab("実験記録を選択すると、登録ファイルがここに表示されます。"),
            "ファイル",
        )
        self.detail_tabs.addTab(
            self.empty_tab("実験記録を選択すると、raw_path のCSVと簡易グラフがここに表示されます。"),
            "CSV/グラフ",
        )
        self.current_row = None
        self.edit_button.setEnabled(False)
        self.steps_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.popout_button.setEnabled(False)
        self.detail_title.setText("記録を選択")

    def empty_tab(self, message):
        theme = self._theme()
        page = QWidget()
        page.setStyleSheet(f"background: {theme['bg']};")
        layout = QVBoxLayout(page)
        label = QLabel(message)
        label.setStyleSheet(
            f"color: {theme['text_muted']}; padding: 16px;"
        )
        layout.addWidget(label)
        layout.addStretch()
        return page

    def make_scroll_page(self):
        theme = self._theme()
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setStyleSheet(
            f"QScrollArea {{ background: {theme['bg']}; border: none; }}"
        )
        page = QWidget()
        page.setStyleSheet(f"background: {theme['bg']};")
        page.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        area.setWidget(page)
        return area, layout

    def render_detail(self, row):
        self.detail_tabs.clear()
        self.detail_tabs.addTab(self.build_basic_tab(row), "基本情報")
        if self.steps_enabled:
            self.detail_tabs.addTab(self.build_steps_tab(row), "工程")
        self.detail_tabs.addTab(self.build_files_tab(row), "ファイル")
        self.detail_tabs.addTab(self.build_raw_data_tab(row), "CSV/グラフ")
        if self.series_enabled:
            self.detail_tabs.addTab(self.build_series_tab(row), "系列")

    def build_basic_tab(self, row):
        area, layout = self.make_scroll_page()
        title = row.get("run_id", "") or "IDなし"
        heading = QLabel(title)
        heading.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {self._theme()['text']};")
        layout.addWidget(heading)

        grid_box = QFrame()
        grid_box.setObjectName("detailCard")
        grid_box.setStyleSheet(self._card_qss("detailCard"))
        grid = QGridLayout(grid_box)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        for row_index, (label_text, value) in enumerate(record_basic_items(row)):
            label = QLabel(label_text)
            label.setStyleSheet(self._muted_bold_ss())
            value_label = QLabel(str(value))
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            grid.addWidget(label, row_index, 0, alignment=Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value_label, row_index, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(grid_box)
        layout.addStretch()
        return area

    # ── 工程タブ ──────────────────────────────────────

    def build_steps_tab(self, row):
        area, layout = self.make_scroll_page()
        run_id = row.get("run_id", "")
        steps = self.steps_by_run.get(run_id, [])
        if not steps:
            empty = QLabel("この記録には工程が登録されていません。")
            empty.setStyleSheet(self._muted_ss())
            layout.addWidget(empty)
            layout.addStretch()
            return area

        primary_field = STEP_FORM[0][0] if STEP_FORM else "action"
        for step in steps:
            card = QFrame()
            card.setObjectName("stepCard")
            card.setStyleSheet(self._card_qss("stepCard"))
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 6, 10, 6)
            card_layout.setSpacing(2)

            primary_value = step.get(primary_field, "")
            icon = icon_for_action(primary_value)
            step_no = step.get("step_no", "")
            header = QLabel(f"{icon} {step_no}. {primary_value}")
            header.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {self._theme()['text']};")
            card_layout.addWidget(header)

            sub_parts = []
            for field, label in STEP_FORM[1:]:
                value = (step.get(field, "") or "").strip()
                if value and field != "notes":
                    sub_parts.append(f"{label}: {value}")
            if sub_parts:
                sub = QLabel(" · ".join(sub_parts))
                sub.setWordWrap(True)
                sub.setStyleSheet(f"color: {self._theme()['text_muted']}; font-size: 12px;")
                card_layout.addWidget(sub)

            notes = (step.get("notes", "") or "").strip()
            if notes:
                notes_label = QLabel(f"📝 {notes}")
                notes_label.setWordWrap(True)
                notes_label.setStyleSheet(f"color: {self._theme()['text_muted']}; font-size: 12px;")
                card_layout.addWidget(notes_label)

            layout.addWidget(card)
        layout.addStretch()
        return area

    # ── 系列タブ ──────────────────────────────────────

    def build_series_tab(self, row):
        area, layout = self.make_scroll_page()
        sid = (row.get("series_id", "") or "").strip()
        if not sid:
            empty = QLabel("この記録にはシリーズが割り当てられていません。")
            empty.setStyleSheet(self._muted_ss())
            layout.addWidget(empty)
            layout.addStretch()
            return area

        runs = [r for r in self.record_table.rows
                if (r.get("series_id", "") or "").strip() == sid]
        runs.sort(key=lambda x: (x.get("date", ""), x.get("run_id", "")))

        # 概要ヘッダ
        heading = QLabel(f"シリーズ: {sid}")
        heading.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {self._theme()['text']};")
        layout.addWidget(heading)

        dates = [x.get("date", "") for x in runs if x.get("date", "")]
        period = f"{min(dates)} 〜 {max(dates)}" if dates else "—"
        summary = QLabel(f"{len(runs)} 件  |  {period}")
        summary.setStyleSheet(self._muted_ss())
        layout.addWidget(summary)

        # Grade 推移
        if feature_enabled("grading"):
            grade_row = QHBoxLayout()
            grade_row.setSpacing(4)
            grade_label = QLabel("Grade推移:")
            grade_label.setStyleSheet(self._muted_ss())
            grade_row.addWidget(grade_label)
            for i, r_ in enumerate(runs):
                g = (r_.get("grade", "") or "").strip().upper() or "?"
                color = GCOL.get(g, "#888888")
                if i > 0:
                    arrow = QLabel("→")
                    arrow.setStyleSheet(self._muted_ss())
                    grade_row.addWidget(arrow)
                gl = QLabel(g)
                gl.setStyleSheet(f"color: {color}; font-weight: 700;")
                grade_row.addWidget(gl)
            grade_row.addStretch()
            layout.addLayout(grade_row)

        # series.csv の既知マップ
        srow = next(
            (s for s in self.series_rows
             if (s.get("series_id", "") or "").strip() == sid),
            None,
        )
        known_map_fields = [
            ("objective", "目的"),
            ("claim", "主張"),
            ("established_knowns", "確認済み事実"),
            ("unresolved", "未解決"),
            ("my_assessment", "所見"),
        ]
        if srow:
            for key, label in known_map_fields:
                value = (srow.get(key, "") or "").strip()
                if value:
                    kl = QLabel(label)
                    kl.setStyleSheet(
                        f"color: {self._theme()['text_muted']}; font-weight: 600; margin-top: 6px;"
                    )
                    layout.addWidget(kl)
                    vl = QLabel(value)
                    vl.setWordWrap(True)
                    vl.setTextInteractionFlags(
                        Qt.TextInteractionFlag.TextSelectableByMouse
                    )
                    layout.addWidget(vl)
        else:
            note = QLabel("このシリーズは series.csv に未登録です。シリーズ管理から登録できます。")
            note.setStyleSheet(self._muted_ss())
            note.setWordWrap(True)
            layout.addWidget(note)

        # 差分タイムライン
        tl_label = QLabel("タイムライン")
        tl_label.setStyleSheet(f"color: {self._theme()['text_muted']}; font-weight: 600; margin-top: 10px;")
        layout.addWidget(tl_label)

        prev_params = None
        current_run_id = row.get("run_id", "")
        for x in runs:
            is_current = x.get("run_id", "") == current_run_id
            box = QFrame()
            box.setObjectName("tlCard")
            _t = self._theme()
            if is_current:
                bg = "#EFF6FF" if not self.dark else "#1A3A5C"
            else:
                bg = _t["bg"]
            box.setStyleSheet(
                f"""
                QFrame#tlCard {{
                    border: 1px solid {_t['border']};
                    border-radius: 6px;
                    background: {bg};
                    margin-bottom: 2px;
                }}
                """
            )
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(10, 6, 10, 6)
            box_layout.setSpacing(2)

            marker = "▶ " if is_current else "   "
            header_parts = [f"{marker}{x.get('date', '')}  {x.get('run_id', '')}"]
            hl = QLabel(header_parts[0])
            weight = "font-weight: 700;" if is_current else ""
            hl.setStyleSheet(f"{weight} font-size: 13px; color: {self._theme()['text']};")

            header_line = QHBoxLayout()
            header_line.setSpacing(6)
            header_line.addWidget(hl)
            if feature_enabled("grading"):
                g = (x.get("grade", "") or "").strip().upper()
                if g:
                    gl = QLabel(g)
                    gl.setStyleSheet(
                        f"color: {GCOL.get(g, '#888')}; font-weight: 700;"
                    )
                    header_line.addWidget(gl)
            exp = x.get("experimenter", "")
            if exp:
                el = QLabel(exp)
                el.setStyleSheet(self._muted_ss())
                header_line.addWidget(el)
            header_line.addStretch()
            box_layout.addLayout(header_line)

            params = self._run_params(x)
            if prev_params is None:
                init_parts = [f"{k}={v}" for k, v in params.items() if v]
                if init_parts:
                    il = QLabel("初期条件: " + "、".join(init_parts))
                    il.setWordWrap(True)
                    il.setStyleSheet(f"color: {self._theme()['text_muted']}; padding-left: 16px;")
                    box_layout.addWidget(il)
            else:
                diffs = []
                for k in params:
                    a, b = prev_params.get(k, ""), params.get(k, "")
                    if a == b:
                        continue
                    fa, fb = fnum(a), fnum(b)
                    if fa is not None and fb is not None:
                        d = fb - fa
                        diffs.append(f"{k}: {a} → {b} ({d:+g})")
                    else:
                        diffs.append(f"{k}: {a or '—'} → {b or '—'}")
                if diffs:
                    for dt in diffs:
                        dl = QLabel(f"Δ {dt}")
                        dl.setStyleSheet("color: #0E6E8C; padding-left: 16px;")
                        box_layout.addWidget(dl)
                else:
                    nl = QLabel("（変更なし）")
                    nl.setStyleSheet(
                        f"color: {self._theme()['text_muted']}; font-size: 11px; padding-left: 16px;"
                    )
                    box_layout.addWidget(nl)

            rs = (x.get("result_summary", "") or "").strip()
            if rs:
                rl = QLabel(rs)
                rl.setWordWrap(True)
                rl.setStyleSheet(f"color: {self._theme()['text']}; padding-left: 16px;")
                box_layout.addWidget(rl)

            prev_params = params
            layout.addWidget(box)

        layout.addStretch()
        return area

    def _known_series(self):
        """既存のseries_idを重複なしソート済みで返す"""
        seen = set()
        for r in self.record_table.rows:
            sid = (r.get("series_id", "") or "").strip()
            if sid:
                seen.add(sid)
        for s in self.series_rows:
            sid = (s.get("series_id", "") or "").strip()
            if sid:
                seen.add(sid)
        return sorted(seen)

    def _run_params(self, row):
        """比較用パラメータ辞書を返す（系列タイムラインの差分表示用）"""
        excluded = {
            "run_id", "series_id", "date", "experimenter", "grade",
            "result_summary", "notes", "base_row",
        }
        excluded.update(
            k for k in self.record_table.fields if k.endswith("_path")
        )
        params = {}
        steps = self.steps_by_run.get(row.get("run_id", ""), [])
        step_fields = {f for f, _l in STEP_FORM}
        for field in self.record_table.fields:
            if field in excluded or field in LONG_FIELDS:
                continue
            value = row.get(field, "")
            if steps and field in step_fields:
                values = []
                for s in steps:
                    item = (s.get(field, "") or "").strip()
                    if item and item not in values:
                        values.append(item)
                if values:
                    value = " / ".join(values)
            params[field] = value
        return params

    def build_files_tab(self, row):
        area, layout = self.make_scroll_page()
        groups = record_file_entries(row, self.record_table.records_csv)
        if not groups:
            empty = QLabel("この記録にはファイルが登録されていません。")
            empty.setStyleSheet(self._muted_ss())
            layout.addWidget(empty)
            layout.addStretch()
            return area

        # 画像プレビュー（サムネイル）
        image_entries = []
        for _label_text, paths in groups:
            for entry in paths:
                if entry.exists and is_image_path(str(entry.path)):
                    image_entries.append(entry)
        if image_entries:
            img_heading = QLabel(f"画像 ({len(image_entries)})")
            img_heading.setStyleSheet(f"color: {self._theme()['text_muted']}; font-weight: 700;")
            layout.addWidget(img_heading)
            gallery = QWidget()
            gallery_layout = QGridLayout(gallery)
            gallery_layout.setContentsMargins(0, 0, 0, 0)
            gallery_layout.setSpacing(8)
            for idx, entry in enumerate(image_entries):
                thumb_frame = QWidget()
                thumb_vbox = QVBoxLayout(thumb_frame)
                thumb_vbox.setContentsMargins(0, 0, 0, 0)
                thumb_vbox.setSpacing(2)
                pixmap = QPixmap(str(entry.resolved_path))
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        150, 110,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    img_label = QLabel()
                    img_label.setPixmap(scaled)
                    img_label.setCursor(Qt.CursorShape.PointingHandCursor)
                    img_label.mousePressEvent = (
                        lambda _ev, e=entry: self.open_record_file(e)
                    )
                    thumb_vbox.addWidget(img_label)
                fname = Path(str(entry.path).replace("\\", "/")).name
                cap = QLabel(fname)
                cap.setStyleSheet(f"color: {self._theme()['text_muted']}; font-size: 11px;")
                cap.setWordWrap(True)
                cap.setMaximumWidth(150)
                thumb_vbox.addWidget(cap)
                gallery_layout.addWidget(
                    thumb_frame, idx // 3, idx % 3,
                    alignment=Qt.AlignmentFlag.AlignTop,
                )
            layout.addWidget(gallery)

        for label_text, paths in groups:
            group_label = QLabel(f"{label_text} ({len(paths)})")
            group_label.setStyleSheet(f"color: {self._theme()['text_muted']}; font-weight: 700;")
            layout.addWidget(group_label)
            for entry in paths:
                card = QFrame()
                card.setObjectName("fileCard")
                _t = self._theme()
                if entry.exists:
                    background = _t["bg_surface"]
                    border = _t["border"]
                else:
                    background = "#FFF7ED" if not self.dark else "#3D2E1A"
                    border = "#FDBA74"
                card.setStyleSheet(
                    f"""
                    QFrame#fileCard {{
                        border: 1px solid {border};
                        border-radius: 8px;
                        background: {background};
                    }}
                    """
                )
                card.setSizePolicy(
                    QSizePolicy.Policy.Ignored,
                    QSizePolicy.Policy.Fixed,
                )
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(10, 8, 10, 8)
                top_line = QHBoxLayout()
                top_line.setSpacing(8)
                name = QLabel(str(entry.path).replace("\\", "/").split("/")[-1])
                name.setWordWrap(True)
                name.setSizePolicy(
                    QSizePolicy.Policy.Ignored,
                    QSizePolicy.Policy.Preferred,
                )
                name.setStyleSheet("font-weight: 700;")
                status = QLabel("存在します" if entry.exists else "見つかりません")
                status.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Preferred,
                )
                status.setStyleSheet(
                    "color: #166534; font-weight: 700;"
                    if entry.exists
                    else "color: #C2410C; font-weight: 700;"
                )
                open_button = QPushButton("開く")
                open_button.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Fixed,
                )
                open_button.setEnabled(entry.exists)
                open_button.clicked.connect(
                    lambda _checked=False, file_entry=entry: self.open_record_file(file_entry)
                )
                top_line.addWidget(name, stretch=1)
                top_line.addWidget(status)
                top_line.addWidget(open_button)
                full_path = QLabel(str(entry.resolved_path))
                full_path.setWordWrap(True)
                full_path.setSizePolicy(
                    QSizePolicy.Policy.Ignored,
                    QSizePolicy.Policy.Preferred,
                )
                full_path.setStyleSheet(self._muted_ss())
                full_path.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                card_layout.addLayout(top_line)
                card_layout.addWidget(full_path)
                layout.addWidget(card)
        layout.addStretch()
        return area

    def build_raw_data_tab(self, row):
        page = RawDataPreviewWidget(row, self.record_table.records_csv, self)
        return page

    def open_record_file(self, entry):
        if not entry.exists:
            QMessageBox.warning(
                self,
                "ファイルが見つかりません",
                f"ファイルが見つかりません。\n{entry.resolved_path}",
            )
            return
        url = QUrl.fromLocalFile(str(entry.resolved_path))
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                "ファイルを開けません",
                f"ファイルを開けませんでした。\n{entry.resolved_path}",
            )

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
