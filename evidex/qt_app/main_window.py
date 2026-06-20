import copy
import json
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
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
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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

try:
    import matplotlib
    from matplotlib import font_manager
    from matplotlib.figure import Figure
    from matplotlib.ticker import MultipleLocator
    try:
        from matplotlib.backends.backend_qtagg import (
            FigureCanvasQTAgg,
            NavigationToolbar2QT,
        )
    except Exception:
        from matplotlib.backends.backend_qt5agg import (
            FigureCanvasQTAgg,
            NavigationToolbar2QT,
        )

    MPL_AVAILABLE = True
except Exception:
    matplotlib = None
    font_manager = None
    Figure = None
    FigureCanvasQTAgg = None
    NavigationToolbar2QT = None
    MultipleLocator = None
    MPL_AVAILABLE = False

from evidex.core.csv_preview import load_csv_preview
from evidex.core.record_table import (
    default_new_record,
    filter_record_rows,
    load_record_table,
    record_basic_items,
    record_file_entries,
    resolve_record_file_path,
    row_values,
    save_record_rows,
    validate_record_update,
)
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
from evidex.core.attachments import join_paths, split_paths
from evidex.core.fields import (
    ACTION_CHOICES,
    CHOICES,
    FACETS,
    HIDDEN_EDIT_FIELDS,
    LONG_FIELDS,
    GCOL,
    STEP_FORM,
    WAVEFORM,
    feature_enabled,
    get_label,
)
from evidex.core.filtering import fnum, norm, row_matches
from evidex.core.icons import icon_for_action
from evidex.core.i18n import t
from evidex.core.media import is_image_path
from evidex.core.schema import load_schema, pack_resource_dir
from evidex.packs import (
    PackInterface,
    active_pack,
    get_pack_names,
    registry,
)
from evidex.core.pack_ops import (
    _PACK_NAME_RE,
    adapter_summary_lines,
    blank_adapter,
    blank_schema,
    choose_initial_pack,
    csv_guidance_key,
    delete_user_pack,
    duplicate_pack,
    save_user_pack,
    user_pack_dir,
    validate_pack_name,
    validate_schema,
)


# ── テーマカラー ──────────────────────────────────────────
_LIGHT = {
    "bg": "#FFFFFF",
    "bg_alt": "#FAFAFA",
    "bg_surface": "#F6F8FA",
    "text": "#344054",
    "text_muted": "#667085",
    "border": "#D0D7DE",
    "border_light": "#E5E7EB",
    "header_bg": "#EEF2F6",
    "nav_bg": "#FAFAFA",
    "nav_border": "#E5E7EB",
    "selection": "#2563EB",
    "selection_text": "#FFFFFF",
    "selection_border": "#1D4ED8",
    "selection_inactive": "#3B82F6",
    "hover": "#F3F4F6",
    "link": "#2563EB",
    "grade_row": {"A": "#E6F3EA", "B": "#FCF0DC", "C": "#ECEFF1"},
}

_DARK = {
    "bg": "#1E1E1E",
    "bg_alt": "#252526",
    "bg_surface": "#2D2D2D",
    "text": "#D4D4D4",
    "text_muted": "#9D9D9D",
    "border": "#404040",
    "border_light": "#333333",
    "header_bg": "#2D2D2D",
    "nav_bg": "#252526",
    "nav_border": "#333333",
    "selection": "#264F78",
    "selection_text": "#FFFFFF",
    "selection_border": "#1B3A57",
    "selection_inactive": "#2A4A6B",
    "hover": "#2A2D2E",
    "link": "#569CD6",
    "grade_row": {"A": "#1F3B2A", "B": "#4A3A1A", "C": "#2E3439"},
}


def configure_matplotlib_fonts():
    if not MPL_AVAILABLE:
        return
    matplotlib.rcParams["axes.unicode_minus"] = False
    candidates = [
        "Yu Gothic",
        "Yu Gothic UI",
        "Meiryo",
        "MS Gothic",
        "Noto Sans CJK JP",
        "Noto Sans JP",
    ]
    available = {font.name for font in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            matplotlib.rcParams["font.family"] = name
            return


configure_matplotlib_fonts()


def waveform_modes(config):
    modes = config.get("modes", [])
    if modes:
        return modes
    return [
        {
            "id": "all",
            "label": "Channels",
            "y_label": "Value",
            "channels": "all",
        }
    ]


def waveform_mode(config, mode_id):
    modes = waveform_modes(config)
    return next(
        (mode for mode in modes if mode.get("id") == mode_id),
        next(
            (
                mode for mode in modes
                if mode.get("id") == config.get("default_mode")
            ),
            modes[0],
        ),
    )


def waveform_channels(signal, mode):
    selected = mode.get("channels")
    if selected == "all":
        return [channel.name for channel in signal.channels]
    if isinstance(selected, list):
        return selected
    return signal.meta.get("groups", {}).get(mode.get("group", ""), [])


def _popout_nav_btn_ss(dark=False):
    t = _DARK if dark else _LIGHT
    return f"""
    QPushButton {{
        border: 1px solid {t['border']}; border-radius: 6px;
        background: {t['bg']}; color: {t['text']};
        padding: 5px 14px; font-weight: 600;
    }}
    QPushButton:hover {{ background: {t['hover']}; border-color: {t['text_muted']}; }}
    QPushButton:disabled {{ background: {t['bg_alt']}; color: {t['border']}; border-color: {t['border_light']}; }}
    """

def _popout_action_btn_ss(dark=False):
    t = _DARK if dark else _LIGHT
    return f"""
    QPushButton {{
        border: 1px solid {t['border']}; border-radius: 6px;
        background: {t['bg']}; color: {t['text']};
        padding: 6px 16px; font-weight: 600;
    }}
    QPushButton:hover {{ background: {t['hover']}; border-color: {t['text_muted']}; }}
    """


class DetailPopoutWindow(QMainWindow):
    """実験記録の詳細を前後に移動しながら表示する別ウィンドウ。"""

    def __init__(self, parent: "EvidexQtWindow", idx: int):
        super().__init__(parent)
        self.owner = parent
        self.idx = idx
        self.setWindowTitle("実験記録の詳細")
        self.resize(720, 700)
        self.setMinimumSize(560, 480)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── ヘッダー ──
        header_widget = QWidget()
        _t = _DARK if parent.dark else _LIGHT
        header_widget.setStyleSheet(
            f"background: {_t['bg']}; border-bottom: 1px solid {_t['border_light']};"
        )
        header = QHBoxLayout(header_widget)
        header.setContentsMargins(16, 10, 16, 10)
        header.setSpacing(10)

        self.prev_button = QPushButton("<  前へ")
        self.prev_button.setStyleSheet(_popout_nav_btn_ss(parent.dark))
        self.prev_button.setFixedWidth(80)
        self.prev_button.clicked.connect(lambda: self.nav(-1))

        self.run_id_label = QLabel()
        self.run_id_label.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {_t['text']};"
        )
        self.grade_label = QLabel()
        self.grade_label.setStyleSheet("font-size: 13px; font-weight: 700;")
        self.grade_label.setVisible(feature_enabled("grading"))
        self.position_label = QLabel()
        self.position_label.setStyleSheet(
            "color: #98A2B3; font-size: 12px; background: transparent;"
        )

        self.next_button = QPushButton("次へ  >")
        self.next_button.setStyleSheet(_popout_nav_btn_ss(parent.dark))
        self.next_button.setFixedWidth(80)
        self.next_button.clicked.connect(lambda: self.nav(1))

        header.addWidget(self.prev_button)
        header.addWidget(self.run_id_label)
        header.addWidget(self.grade_label)
        header.addWidget(self.position_label)
        header.addStretch()
        header.addWidget(self.next_button)
        layout.addWidget(header_widget)

        # ── タブ本体 ──
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border-top: 1px solid {_t['border_light']}; background: {_t['bg']}; }}
            QTabBar::tab {{
                padding: 8px 18px; font-weight: 600; color: {_t['text_muted']};
                border: none; border-bottom: 2px solid transparent;
                background: {_t['bg']};
            }}
            QTabBar::tab:selected {{
                color: #1D4ED8; border-bottom: 2px solid #1D4ED8;
            }}
            QTabBar::tab:hover {{ color: {_t['text']}; }}
        """)
        layout.addWidget(self.tabs, stretch=1)

        # ── フッター ──
        footer_widget = QWidget()
        footer_widget.setStyleSheet(
            f"background: {_t['bg']}; border-top: 1px solid {_t['border_light']};"
        )
        footer = QHBoxLayout(footer_widget)
        footer.setContentsMargins(16, 8, 16, 8)
        footer.setSpacing(8)
        self.edit_button = QPushButton("記録を編集")
        self.edit_button.setStyleSheet(_popout_action_btn_ss(parent.dark))
        self.edit_button.clicked.connect(self.edit_current)
        footer.addWidget(self.edit_button)
        if self.owner.steps_enabled:
            self.steps_button = QPushButton("工程を編集")
            self.steps_button.setStyleSheet(_popout_action_btn_ss(parent.dark))
            self.steps_button.clicked.connect(self.edit_steps)
            footer.addWidget(self.steps_button)
        footer.addStretch()
        layout.addWidget(footer_widget)

        self.setCentralWidget(root)
        self.render()

    def current_row(self):
        if 0 <= self.idx < len(self.owner.filtered_rows):
            return self.owner.filtered_rows[self.idx]
        return None

    def nav(self, delta):
        new_index = self.idx + delta
        if 0 <= new_index < len(self.owner.filtered_rows):
            self.idx = new_index
            self.render()

    def render(self):
        row = self.current_row()
        if row is None:
            self.close()
            return

        run_id = row.get("run_id", "") or "ID なし"
        self.setWindowTitle(f"{run_id} — Evidex")
        self.run_id_label.setText(run_id)
        if feature_enabled("grading"):
            grade = (row.get("grade", "") or "").strip().upper()
            self.grade_label.setText(grade or "—")
            self.grade_label.setStyleSheet(
                f"color: {GCOL.get(grade, '#98A2B3')};"
                "font-size: 13px; font-weight: 700; background: transparent;"
            )
        total = len(self.owner.filtered_rows)
        self.position_label.setText(f"{self.idx + 1} / {total}")
        self.prev_button.setEnabled(self.idx > 0)
        self.next_button.setEnabled(self.idx < total - 1)

        while self.tabs.count():
            page = self.tabs.widget(0)
            self.tabs.removeTab(0)
            page.deleteLater()
        self.tabs.addTab(self.owner.build_basic_tab(row), "基本情報")
        if self.owner.steps_enabled:
            self.tabs.addTab(self.owner.build_steps_tab(row), "工程")
        self.tabs.addTab(self.owner.build_files_tab(row), "ファイル")
        if self.owner.series_enabled:
            self.tabs.addTab(self.owner.build_series_tab(row), "系列")

    def edit_current(self):
        row = self.current_row()
        if row is None:
            return
        self.close()
        self.owner.edit_run(row)

    def edit_steps(self):
        row = self.current_row()
        if row is None:
            return
        run_id = row.get("run_id", "")
        self.close()
        self.owner.open_steps_editor(run_id)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self.nav(-1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self.nav(1)
            event.accept()
            return
        super().keyPressEvent(event)


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
        """パックの作成・編集・複製・削除を行うダイアログを表示する。"""
        from evidex.core import config, settings

        dialog = QDialog(self)
        dialog.setWindowTitle("パック管理")
        dialog.resize(960, 640)
        dialog.setMinimumSize(680, 480)

        main_layout = QHBoxLayout(dialog)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        state = {
            "schema": {},
            "adapter": {},
            "viz": {},
            "builtin": True,
            "python_adapter": False,
        }

        # ── 左パネル: パック一覧 ──
        left = QWidget()
        left.setFixedWidth(200)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("パック一覧"))

        pack_list = QListWidget()
        pack_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        left_layout.addWidget(pack_list, stretch=1)

        btn_row1 = QHBoxLayout()
        new_btn = QPushButton("新規作成")
        dup_btn = QPushButton("複製")
        del_btn = QPushButton("削除")
        btn_row1.addWidget(new_btn)
        btn_row1.addWidget(dup_btn)
        btn_row1.addWidget(del_btn)
        left_layout.addLayout(btn_row1)

        main_layout.addWidget(left)

        # ── 右パネル: タブ付きエディタ ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("編集中:"))
        pack_name_label = QLabel("")
        pack_name_label.setStyleSheet("font-weight: bold;")
        top_row.addWidget(pack_name_label, stretch=1)
        active_label = QLabel("")
        active_label.setStyleSheet("color: #2563EB;")
        top_row.addWidget(active_label)
        right_layout.addLayout(top_row)

        tabs = QTabWidget()
        right_layout.addWidget(tabs, stretch=1)

        bottom_row = QHBoxLayout()
        readonly_label = QLabel("")
        readonly_label.setStyleSheet("color: #888;")
        bottom_row.addWidget(readonly_label, stretch=1)
        save_btn = QPushButton("保存")
        save_btn.setEnabled(False)
        bottom_row.addWidget(save_btn)
        right_layout.addLayout(bottom_row)

        main_layout.addWidget(right, stretch=1)

        # ── タブ1: フィールド ──
        fields_page = QWidget()
        fields_layout = QHBoxLayout(fields_page)

        field_left = QWidget()
        fl_layout = QVBoxLayout(field_left)
        fl_layout.setContentsMargins(0, 0, 0, 0)

        field_table = QTableWidget()
        field_table.setColumnCount(5)
        field_table.setHorizontalHeaderLabels(
            ["ID", "日本語名", "英語名", "入力方式", "選択肢"]
        )
        field_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        field_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        field_table.horizontalHeader().setStretchLastSection(True)
        fl_layout.addWidget(field_table, stretch=1)

        field_btns = QHBoxLayout()
        add_field_btn = QPushButton("追加")
        up_field_btn = QPushButton("▲")
        down_field_btn = QPushButton("▼")
        del_field_btn = QPushButton("削除")
        field_btns.addWidget(add_field_btn)
        field_btns.addWidget(up_field_btn)
        field_btns.addWidget(down_field_btn)
        field_btns.addStretch()
        field_btns.addWidget(del_field_btn)
        fl_layout.addLayout(field_btns)
        fields_layout.addWidget(field_left, stretch=2)

        field_form = QGroupBox("フィールド編集")
        ff_layout = QFormLayout(field_form)
        field_id_edit = QLineEdit()
        field_jp_edit = QLineEdit()
        field_en_edit = QLineEdit()
        type_labels = {
            "text": "テキスト",
            "number": "数値",
            "date": "日付",
            "choice": "選択肢",
        }
        type_ids = {value: key for key, value in type_labels.items()}
        field_type_combo = QComboBox()
        field_type_combo.addItems(list(type_labels.values()))
        field_choices_edit = QLineEdit()
        field_choices_edit.setPlaceholderText("カンマ区切り")
        apply_field_btn = QPushButton("適用")
        ff_layout.addRow("フィールドID:", field_id_edit)
        ff_layout.addRow("日本語名:", field_jp_edit)
        ff_layout.addRow("英語名:", field_en_edit)
        ff_layout.addRow("入力方式:", field_type_combo)
        ff_layout.addRow("選択肢:", field_choices_edit)
        ff_layout.addRow("", apply_field_btn)
        fields_layout.addWidget(field_form, stretch=1)

        tabs.addTab(fields_page, "フィールド")

        def field_kind(schema, field):
            if field in schema.get("CHOICES", {}):
                return "choice"
            return schema.get("FIELD_TYPES", {}).get(field, "text")

        def reload_field_table(select_index=None):
            field_table.blockSignals(True)
            field_table.setRowCount(0)
            schema = state["schema"]
            for field in schema.get("RUN_FIELDS", []):
                choices = schema.get("CHOICES", {}).get(field, [])
                row = field_table.rowCount()
                field_table.insertRow(row)
                field_table.setItem(row, 0, QTableWidgetItem(field))
                field_table.setItem(
                    row,
                    1,
                    QTableWidgetItem(
                        schema.get("JP_LABEL", {}).get(field, "")
                    ),
                )
                field_table.setItem(
                    row,
                    2,
                    QTableWidgetItem(
                        schema.get("LABEL_EN", {}).get(field, "")
                    ),
                )
                field_table.setItem(
                    row,
                    3,
                    QTableWidgetItem(
                        type_labels.get(
                            field_kind(schema, field),
                            "テキスト",
                        )
                    ),
                )
                field_table.setItem(
                    row,
                    4,
                    QTableWidgetItem(", ".join(choices)),
                )
            field_table.blockSignals(False)
            if select_index is not None and field_table.rowCount() > 0:
                index = max(
                    0,
                    min(select_index, field_table.rowCount() - 1),
                )
                field_table.selectRow(index)
                on_field_select()

        def on_field_select():
            row = field_table.currentRow()
            if row < 0:
                return
            schema = state["schema"]
            fields = schema.get("RUN_FIELDS", [])
            if row >= len(fields):
                return
            field = fields[row]
            field_id_edit.setText(field)
            field_jp_edit.setText(
                schema.get("JP_LABEL", {}).get(field, "")
            )
            field_en_edit.setText(
                schema.get("LABEL_EN", {}).get(field, "")
            )
            kind = field_kind(schema, field)
            field_type_combo.setCurrentText(
                type_labels.get(kind, "テキスト")
            )
            field_choices_edit.setText(
                ",".join(schema.get("CHOICES", {}).get(field, []))
            )

        field_table.itemSelectionChanged.connect(on_field_select)

        def apply_field_edit():
            row = field_table.currentRow()
            if row < 0 or state["builtin"]:
                return
            schema = state["schema"]
            old_id = schema["RUN_FIELDS"][row]
            new_id = field_id_edit.text().strip()
            if not new_id or not _PACK_NAME_RE.fullmatch(new_id):
                QMessageBox.warning(
                    dialog,
                    "エラー",
                    "フィールドIDが不正です。英数字と_-のみ使用可能。",
                )
                return
            if new_id != old_id and new_id in schema["RUN_FIELDS"]:
                QMessageBox.warning(
                    dialog,
                    "エラー",
                    "同じIDのフィールドが既に存在します。",
                )
                return
            schema["RUN_FIELDS"][row] = new_id
            for key in (
                "JP_LABEL",
                "LABEL_EN",
                "FIELD_TYPES",
                "CHOICES",
            ):
                schema.setdefault(key, {})
            schema["JP_LABEL"][new_id] = field_jp_edit.text().strip()
            schema["LABEL_EN"][new_id] = field_en_edit.text().strip()
            kind = type_ids.get(
                field_type_combo.currentText(),
                "text",
            )
            schema["FIELD_TYPES"][new_id] = kind
            if kind == "choice":
                schema["CHOICES"][new_id] = [
                    value.strip()
                    for value in field_choices_edit.text().split(",")
                    if value.strip()
                ]
            else:
                schema["CHOICES"].pop(new_id, None)
            if old_id != new_id:
                for key in (
                    "JP_LABEL",
                    "LABEL_EN",
                    "FIELD_TYPES",
                    "CHOICES",
                ):
                    schema[key].pop(old_id, None)
                schema["COLS"] = [
                    [new_id if column == old_id else column, width]
                    for column, width in schema.get("COLS", [])
                ]
                if old_id in schema.get("HEAD", {}):
                    schema["HEAD"][new_id] = schema["HEAD"].pop(old_id)
                for facet in schema.get("facets", []):
                    if facet.get("field") == old_id:
                        facet["field"] = new_id
            reload_field_table(row)

        apply_field_btn.clicked.connect(apply_field_edit)

        def add_field():
            if state["builtin"]:
                return
            schema = state["schema"]
            base = "new_field"
            candidate = base
            suffix = 2
            while candidate in schema["RUN_FIELDS"]:
                candidate = f"{base}_{suffix}"
                suffix += 1
            schema["RUN_FIELDS"].append(candidate)
            schema.setdefault("JP_LABEL", {})[candidate] = candidate
            schema.setdefault("LABEL_EN", {})[candidate] = candidate
            schema.setdefault("FIELD_TYPES", {})[candidate] = "text"
            reload_field_table(len(schema["RUN_FIELDS"]) - 1)

        def delete_field():
            row = field_table.currentRow()
            if row < 0 or state["builtin"]:
                return
            schema = state["schema"]
            field = schema["RUN_FIELDS"][row]
            if field == "run_id":
                QMessageBox.warning(
                    dialog,
                    "エラー",
                    "run_id は削除できません。",
                )
                return
            schema["RUN_FIELDS"].pop(row)
            for key in (
                "JP_LABEL",
                "LABEL_EN",
                "FIELD_TYPES",
                "CHOICES",
            ):
                schema.setdefault(key, {}).pop(field, None)
            schema["COLS"] = [
                item
                for item in schema.get("COLS", [])
                if item[0] != field
            ]
            schema.get("HEAD", {}).pop(field, None)
            schema["facets"] = [
                facet
                for facet in schema.get("facets", [])
                if facet.get("field") != field
            ]
            reload_field_table(row)

        def move_field(delta):
            row = field_table.currentRow()
            if row < 0 or state["builtin"]:
                return
            fields = state["schema"]["RUN_FIELDS"]
            target = row + delta
            if target < 0 or target >= len(fields):
                return
            fields[row], fields[target] = fields[target], fields[row]
            reload_field_table(target)

        add_field_btn.clicked.connect(add_field)
        del_field_btn.clicked.connect(delete_field)
        up_field_btn.clicked.connect(lambda: move_field(-1))
        down_field_btn.clicked.connect(lambda: move_field(1))

        # ── タブ2: アダプター設定 ──
        adapter_page = QScrollArea()
        adapter_page.setWidgetResizable(True)
        adapter_page.setFrameShape(QFrame.Shape.NoFrame)
        adapter_content = QWidget()
        adapter_layout = QVBoxLayout(adapter_content)

        current_settings_label = QLabel("")
        current_settings_label.setWordWrap(True)
        current_settings_label.setStyleSheet(
            "padding: 8px; background: #f8f8f8; border-radius: 4px;"
        )
        adapter_layout.addWidget(current_settings_label)

        csv_row = QHBoxLayout()
        choose_csv_btn = QPushButton("CSVを選択...")
        csv_path_label = QLabel("")
        csv_info_label = QLabel("")
        csv_info_label.setStyleSheet("color: #777;")
        csv_row.addWidget(choose_csv_btn)
        csv_row.addWidget(csv_path_label, stretch=1)
        csv_row.addWidget(csv_info_label)
        adapter_layout.addLayout(csv_row)

        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel("スキップ行数:"))
        skip_rows_edit = QLineEdit("0")
        skip_rows_edit.setFixedWidth(60)
        opt_row.addWidget(skip_rows_edit)
        opt_row.addWidget(QLabel("区切り文字:"))
        delimiter_combo = QComboBox()
        delimiter_combo.addItems([",", ";", "\\t"])
        delimiter_combo.setFixedWidth(80)
        opt_row.addWidget(delimiter_combo)
        reload_cols_btn = QPushButton("列を再読込")
        opt_row.addWidget(reload_cols_btn)
        opt_row.addStretch()
        adapter_layout.addLayout(opt_row)

        python_adapter_note = QLabel("")
        python_adapter_note.setWordWrap(True)
        python_adapter_note.setStyleSheet("color: #555;")
        adapter_layout.addWidget(python_adapter_note)

        x_group = QGroupBox("X軸設定")
        x_layout = QFormLayout(x_group)
        x_column_combo = QComboBox()
        x_name_edit = QLineEdit()
        x_unit_edit = QLineEdit()
        x_layout.addRow("X軸列:", x_column_combo)
        x_layout.addRow("軸名:", x_name_edit)
        x_layout.addRow("単位:", x_unit_edit)
        adapter_layout.addWidget(x_group)

        ch_group = QGroupBox("チャンネル設定")
        ch_layout = QVBoxLayout(ch_group)
        ch_layout.addWidget(
            QLabel(
                "X軸列以外の列がチャンネル候補になります。"
                "チェックした列を使用します。"
            )
        )

        channel_table = QTableWidget()
        channel_table.setColumnCount(3)
        channel_table.setHorizontalHeaderLabels(["使用", "列名", "単位"])
        channel_table.horizontalHeader().setStretchLastSection(True)
        channel_table.setColumnWidth(0, 40)
        channel_table.setColumnWidth(1, 200)
        ch_layout.addWidget(channel_table, stretch=1)

        ch_btns = QHBoxLayout()
        ch_select_all = QPushButton("全選択")
        ch_clear_all = QPushButton("全解除")
        ch_btns.addWidget(ch_select_all)
        ch_btns.addWidget(ch_clear_all)

        ch_unit_row = QHBoxLayout()
        ch_unit_row.addWidget(QLabel("選択列の単位:"))
        ch_unit_edit = QLineEdit()
        ch_unit_edit.setFixedWidth(100)
        ch_unit_row.addWidget(ch_unit_edit)
        ch_apply_unit = QPushButton("適用")
        ch_unit_row.addWidget(ch_apply_unit)
        ch_unit_row.addStretch()
        ch_btns.addStretch()
        ch_btns.addLayout(ch_unit_row)
        ch_layout.addLayout(ch_btns)
        adapter_layout.addWidget(ch_group)

        adapter_btns = QHBoxLayout()
        apply_adapter_btn = QPushButton("設定を適用")
        test_adapter_btn = QPushButton("テスト読込")
        adapter_btns.addWidget(apply_adapter_btn)
        adapter_btns.addWidget(test_adapter_btn)
        adapter_btns.addStretch()
        adapter_layout.addLayout(adapter_btns)

        adapter_page.setWidget(adapter_content)
        tabs.addTab(adapter_page, "アダプター設定")

        adapter_headers = []
        channel_units_map = {}

        def delimiter_value():
            value = delimiter_combo.currentText()
            return "\t" if value == "\\t" else value

        def delimiter_label(value):
            return "\\t" if value == "\t" else value

        def parse_skip_rows():
            try:
                value = int(skip_rows_edit.text().strip() or "0")
                if value < 0:
                    raise ValueError
                return value
            except ValueError:
                QMessageBox.warning(
                    dialog,
                    "エラー",
                    "スキップ行数は0以上の整数を指定してください。",
                )
                return None

        def refresh_current_settings():
            lines = []
            for item in adapter_summary_lines(
                state.get("adapter") or {},
                state.get("python_adapter", False),
            ):
                if isinstance(item, tuple):
                    key, values = item
                    lines.append(t(key, **values))
                else:
                    lines.append(t(item))
            current_settings_label.setText("\n".join(lines))

        def reload_channel_table(headers, selected_names=None):
            selected_names = set(selected_names or [])
            x_column = x_column_combo.currentText()
            channel_table.setRowCount(0)
            for name in headers:
                if name == x_column:
                    continue
                row = channel_table.rowCount()
                channel_table.insertRow(row)
                checkbox = QCheckBox()
                checkbox.setChecked(name in selected_names)
                channel_table.setCellWidget(row, 0, checkbox)
                channel_table.setItem(row, 1, QTableWidgetItem(name))
                channel_table.setItem(
                    row,
                    2,
                    QTableWidgetItem(channel_units_map.get(name, "")),
                )

        def selected_channel_names():
            names = []
            for row in range(channel_table.rowCount()):
                checkbox = channel_table.cellWidget(row, 0)
                if checkbox and checkbox.isChecked():
                    item = channel_table.item(row, 1)
                    if item:
                        names.append(item.text())
            return names

        def load_csv_columns(path=None, auto_detect=True):
            nonlocal adapter_headers
            if not path:
                path, _ = QFileDialog.getOpenFileName(
                    dialog,
                    "CSVファイルを選択",
                    "",
                    "CSV Files (*.csv);;All Files (*)",
                )
            if not path:
                return False
            skip = parse_skip_rows()
            if skip is None:
                return False
            try:
                from evidex.core.nocode_adapter import inspect_csv

                inspected = inspect_csv(
                    path,
                    skip_rows=skip,
                    delimiter=None if auto_detect else delimiter_value(),
                )
            except Exception as error:
                QMessageBox.critical(
                    dialog,
                    "読み込みエラー",
                    str(error),
                )
                return False

            csv_path_label.setText(str(path))
            delimiter_combo.setCurrentText(
                delimiter_label(inspected["delimiter"])
            )
            csv_info_label.setText(
                f"エンコーディング: {inspected['encoding']}, "
                f"列数: {len(inspected['header'])}"
            )
            adapter_headers = list(inspected["header"])
            previous_x = x_column_combo.currentText()
            x_column_combo.clear()
            x_column_combo.addItems(adapter_headers)
            if previous_x in adapter_headers:
                x_column_combo.setCurrentText(previous_x)
            elif adapter_headers:
                x_column_combo.setCurrentIndex(0)
            if not x_name_edit.text().strip():
                x_name_edit.setText(x_column_combo.currentText())
            configured = state.get("adapter") or {}
            selected = [
                name
                for name in configured.get("channel_columns", [])
                if (
                    name in adapter_headers
                    and name != x_column_combo.currentText()
                )
            ]
            if not selected:
                selected = [
                    name
                    for name in adapter_headers
                    if name != x_column_combo.currentText()
                ]
            reload_channel_table(adapter_headers, selected)
            return True

        choose_csv_btn.clicked.connect(
            lambda: load_csv_columns(auto_detect=True)
        )
        reload_cols_btn.clicked.connect(
            lambda: load_csv_columns(
                csv_path_label.text() or None,
                auto_detect=False,
            )
        )

        def on_x_column_changed():
            selected = selected_channel_names()
            reload_channel_table(adapter_headers, selected)
            if not x_name_edit.text().strip():
                x_name_edit.setText(x_column_combo.currentText())

        x_column_combo.currentTextChanged.connect(on_x_column_changed)

        def ch_toggle_all(checked):
            for row in range(channel_table.rowCount()):
                checkbox = channel_table.cellWidget(row, 0)
                if checkbox:
                    checkbox.setChecked(checked)

        ch_select_all.clicked.connect(lambda: ch_toggle_all(True))
        ch_clear_all.clicked.connect(lambda: ch_toggle_all(False))

        def apply_channel_unit():
            unit = ch_unit_edit.text().strip()
            for row in range(channel_table.rowCount()):
                checkbox = channel_table.cellWidget(row, 0)
                if checkbox and checkbox.isChecked():
                    channel_table.setItem(
                        row,
                        2,
                        QTableWidgetItem(unit),
                    )
                    name_item = channel_table.item(row, 1)
                    if name_item:
                        channel_units_map[name_item.text()] = unit

        ch_apply_unit.clicked.connect(apply_channel_unit)

        def apply_adapter_edit():
            x_column = x_column_combo.currentText().strip()
            channels = selected_channel_names()
            if state["python_adapter"] and not x_column and not channels:
                state["adapter"] = None
                refresh_current_settings()
                return True
            if not x_column or not channels:
                QMessageBox.warning(
                    dialog,
                    "エラー",
                    "X軸列とチャンネル列を1つ以上選択してください。",
                )
                return False
            skip = parse_skip_rows()
            if skip is None:
                return False
            delimiter = delimiter_value()
            if len(delimiter) != 1:
                QMessageBox.warning(
                    dialog,
                    "エラー",
                    "区切り文字は1文字にしてください。",
                )
                return False

            channel_units = []
            for name in channels:
                for row in range(channel_table.rowCount()):
                    name_item = channel_table.item(row, 1)
                    if name_item and name_item.text() == name:
                        unit_item = channel_table.item(row, 2)
                        channel_units_map[name] = (
                            unit_item.text() if unit_item else ""
                        )
                        break
                channel_units.append(channel_units_map.get(name, ""))

            state["adapter"] = {
                "file_format": "csv",
                "encoding_fallback": ["utf-8-sig", "cp932"],
                "skip_rows": skip,
                "x_column": x_column,
                "x_name": x_name_edit.text().strip(),
                "x_unit": x_unit_edit.text().strip(),
                "channel_columns": channels,
                "channel_units": channel_units,
                "delimiter": delimiter,
            }
            refresh_current_settings()
            return True

        apply_adapter_btn.clicked.connect(apply_adapter_edit)

        def test_parse():
            path = csv_path_label.text()
            if not path and not load_csv_columns(auto_detect=True):
                return
            path = csv_path_label.text()
            if not apply_adapter_edit():
                return
            try:
                item = pack_list.currentItem()
                pack_name = item.text() if item else ""
                if state["adapter"] is None:
                    if pack_name in registry:
                        import importlib

                        module = importlib.import_module(
                            registry[pack_name]
                        )
                        pack = PackInterface(pack_name, module=module)
                    else:
                        pack = PackInterface(
                            pack_name,
                            user_path=str(user_pack_dir(pack_name)),
                        )
                    signal = pack.parse(path)
                else:
                    from evidex.core.nocode_adapter import (
                        parse_with_config,
                    )

                    signal = parse_with_config(path, state["adapter"])
                QMessageBox.information(
                    dialog,
                    "テスト成功",
                    f"読込成功: {len(signal.x.values)}ポイント, "
                    f"{len(signal.channels)}チャンネル",
                )
            except Exception as error:
                QMessageBox.critical(
                    dialog,
                    "テスト失敗",
                    str(error),
                )

        test_adapter_btn.clicked.connect(test_parse)

        # ── タブ3: 表示設定 ──
        display_page = QScrollArea()
        display_page.setWidgetResizable(True)
        display_page.setFrameShape(QFrame.Shape.NoFrame)
        display_content = QWidget()
        display_layout = QVBoxLayout(display_content)

        facet_group = QGroupBox("ナビゲーション ファセット")
        facet_layout = QVBoxLayout(facet_group)
        facet_layout.addWidget(
            QLabel("ナビパネルに表示するフィールドを選択:")
        )
        facet_list = QListWidget()
        facet_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        facet_layout.addWidget(facet_list)
        display_layout.addWidget(facet_group)

        feature_group = QGroupBox("機能")
        feat_layout = QVBoxLayout(feature_group)
        feature_checks = {}
        feature_descs = {
            "steps": (
                "工程管理",
                "実験の各工程を記録・管理します",
            ),
            "series": (
                "シリーズ管理",
                "複数の実験をシリーズとしてグループ化します",
            ),
            "grading": (
                "グレード評価",
                "実験結果をA/B/Cでグレード付けします",
            ),
            "baseline": (
                "ベースライン",
                "波形のベースライン補正を有効にします",
            ),
        }
        for name, (label, description) in feature_descs.items():
            checkbox = QCheckBox(label)
            feature_checks[name] = checkbox
            feat_layout.addWidget(checkbox)
            desc_label = QLabel(description)
            desc_label.setStyleSheet(
                "color: #666; padding-left: 24px;"
            )
            feat_layout.addWidget(desc_label)
        display_layout.addWidget(feature_group)

        color_group = QGroupBox("Grade 色")
        color_layout = QFormLayout(color_group)
        color_edits = {}
        for grade in "ABC":
            edit = QLineEdit("#808080")
            edit.setFixedWidth(100)
            color_edits[grade] = edit
            color_layout.addRow(f"Grade {grade}:", edit)
        display_layout.addWidget(color_group)

        apply_display_btn = QPushButton("表示設定を適用")
        display_layout.addWidget(
            apply_display_btn,
            alignment=Qt.AlignmentFlag.AlignRight,
        )

        display_page.setWidget(display_content)
        tabs.addTab(display_page, "表示設定")

        def reload_facets():
            facet_list.clear()
            schema = state["schema"]
            enabled = {
                facet.get("field")
                for facet in schema.get("facets", [])
            }
            for field in schema.get("RUN_FIELDS", []):
                label = (
                    schema.get("JP_LABEL", {}).get(field)
                    or schema.get("LABEL_EN", {}).get(field)
                    or field
                )
                item = QListWidgetItem(f"{label}  ({field})")
                item.setData(Qt.ItemDataRole.UserRole, field)
                facet_list.addItem(item)
                if field in enabled:
                    item.setSelected(True)

        def apply_display_edit():
            import re as re_mod

            schema = state["schema"]
            previous = {
                facet.get("field"): facet
                for facet in schema.get("facets", [])
            }
            facets = []
            for index in range(facet_list.count()):
                item = facet_list.item(index)
                if item.isSelected():
                    field = item.data(Qt.ItemDataRole.UserRole)
                    facets.append(
                        previous.get(
                            field,
                            {
                                "field": field,
                                "label_key": "",
                                "source": (
                                    "choices"
                                    if field
                                    in schema.get("CHOICES", {})
                                    else "data"
                                ),
                                "match": "exact",
                            },
                        )
                    )
            colors = {}
            features = {
                name: checkbox.isChecked()
                for name, checkbox in feature_checks.items()
            }
            if features["grading"]:
                for grade in "ABC":
                    value = color_edits[grade].text().strip()
                    if not re_mod.fullmatch(
                        r"#[0-9A-Fa-f]{6}",
                        value,
                    ):
                        QMessageBox.warning(
                            dialog,
                            "エラー",
                            f"Grade {grade} の色が不正です。"
                            "#RRGGBB形式で入力してください。",
                        )
                        return False
                    colors[grade] = value.upper()
            schema["facets"] = facets
            schema["GCOL"] = colors
            schema["features"] = features
            state["viz"] = {
                "facets": copy.deepcopy(facets),
                "GCOL": colors.copy(),
            }
            return True

        apply_display_btn.clicked.connect(apply_display_edit)

        # ── パック読み込み・保存・作成・複製・削除 ──
        def load_pack(pack_name):
            builtin = pack_name in registry
            try:
                if builtin:
                    schema = load_schema(pack_name)
                    base = pack_resource_dir(pack_name)
                else:
                    base = user_pack_dir(pack_name)
                    with (base / "schema.json").open(
                        "r",
                        encoding="utf-8",
                    ) as handle:
                        schema = json.load(handle)
                adapter = {}
                adapter_path = base / "adapter_config.json"
                if adapter_path.is_file():
                    with adapter_path.open(
                        "r",
                        encoding="utf-8",
                    ) as handle:
                        adapter = json.load(handle)
                viz = {}
                viz_path = base / "viz.json"
                if viz_path.is_file():
                    with viz_path.open(
                        "r",
                        encoding="utf-8",
                    ) as handle:
                        viz = json.load(handle)
            except Exception as error:
                QMessageBox.critical(
                    dialog,
                    "読み込みエラー",
                    str(error),
                )
                return

            state.update(
                schema=copy.deepcopy(schema),
                adapter=copy.deepcopy(adapter),
                viz=copy.deepcopy(viz),
                builtin=builtin,
                python_adapter=(base / "adapter.py").is_file(),
            )
            pack_name_label.setText(pack_name)
            active_name = settings.get(
                "active_pack",
                config.DEFAULT_PACK,
            )
            active_label.setText(
                "（アクティブ）"
                if pack_name == active_name
                else ""
            )
            readonly_label.setText(
                "組み込みパック（読み取り専用）"
                if builtin
                else ""
            )

            reload_field_table(0)

            adapter_headers.clear()
            x_column = adapter.get("x_column", "")
            configured_columns = list(
                adapter.get("channel_columns", [])
            )
            columns = [x_column] if x_column else []
            columns.extend(
                name
                for name in configured_columns
                if name not in columns
            )
            adapter_headers.extend(columns)
            x_column_combo.clear()
            x_column_combo.addItems(columns)
            if x_column:
                x_column_combo.setCurrentText(x_column)
            x_name_edit.setText(str(adapter.get("x_name", "")))
            x_unit_edit.setText(str(adapter.get("x_unit", "")))
            skip_rows_edit.setText(
                str(adapter.get("skip_rows", 0))
            )
            delimiter_combo.setCurrentText(
                delimiter_label(adapter.get("delimiter", ","))
            )
            csv_path_label.setText("")
            csv_info_label.setText("")
            channel_units_map.clear()
            configured_units = list(
                adapter.get("channel_units", [])
            )
            channel_units_map.update(
                {
                    name: (
                        configured_units[index]
                        if index < len(configured_units)
                        else ""
                    )
                    for index, name in enumerate(configured_columns)
                }
            )
            reload_channel_table(
                adapter_headers,
                configured_columns,
            )
            python_adapter_note.setText(
                t(
                    csv_guidance_key(
                        pack_name,
                        state["python_adapter"],
                    )
                )
            )
            refresh_current_settings()

            for grade in "ABC":
                color_edits[grade].setText(
                    schema.get("GCOL", {}).get(
                        grade,
                        "#808080",
                    )
                )
            features = schema.get("features", {})
            for name, checkbox in feature_checks.items():
                checkbox.setChecked(
                    bool(features.get(name, False))
                )
            reload_facets()

            editable = not builtin
            save_btn.setEnabled(editable)
            apply_field_btn.setEnabled(editable)
            apply_display_btn.setEnabled(editable)
            add_field_btn.setEnabled(editable)
            del_field_btn.setEnabled(editable)
            up_field_btn.setEnabled(editable)
            down_field_btn.setEnabled(editable)
            apply_adapter_btn.setEnabled(editable)
            test_adapter_btn.setEnabled(editable)
            choose_csv_btn.setEnabled(editable)
            reload_cols_btn.setEnabled(editable)
            ch_select_all.setEnabled(editable)
            ch_clear_all.setEnabled(editable)
            ch_apply_unit.setEnabled(editable)
            del_btn.setEnabled(editable)
            field_id_edit.setReadOnly(not editable)
            field_jp_edit.setReadOnly(not editable)
            field_en_edit.setReadOnly(not editable)
            field_type_combo.setEnabled(editable)
            field_choices_edit.setReadOnly(not editable)
            skip_rows_edit.setReadOnly(not editable)
            delimiter_combo.setEnabled(editable)
            x_column_combo.setEnabled(editable)
            x_name_edit.setReadOnly(not editable)
            x_unit_edit.setReadOnly(not editable)
            ch_unit_edit.setReadOnly(not editable)
            facet_list.setEnabled(editable)
            feature_group.setEnabled(editable)
            color_group.setEnabled(editable)

        def refresh_pack_list(select_name=None):
            names = get_pack_names()
            selected_item = pack_list.currentItem()
            previous_name = (
                selected_item.text() if selected_item else ""
            )
            pack_list.blockSignals(True)
            pack_list.clear()
            pack_list.addItems(names)
            target = choose_initial_pack(
                names,
                select_name or previous_name,
                settings.get(
                    "active_pack",
                    config.DEFAULT_PACK,
                ),
            )
            if target and target in names:
                pack_list.setCurrentRow(names.index(target))
            pack_list.blockSignals(False)
            if target:
                load_pack(target)

        def on_pack_select():
            item = pack_list.currentItem()
            if item:
                load_pack(item.text())

        pack_list.currentItemChanged.connect(
            lambda _current, _previous: on_pack_select()
        )

        def save_current():
            try:
                if not apply_adapter_edit() or not apply_display_edit():
                    return
                item = pack_list.currentItem()
                if not item:
                    return
                name = item.text()
                validate_schema(state["schema"])
                save_user_pack(
                    name,
                    state["schema"],
                    state["adapter"],
                    state["viz"],
                )
                use = (
                    QMessageBox.question(
                        dialog,
                        "保存完了",
                        f"パック '{name}' を保存しました。"
                        "このパックをアクティブにしますか？",
                    )
                    == QMessageBox.StandardButton.Yes
                )
                if use:
                    settings.set("active_pack", name)
                    QMessageBox.information(
                        dialog,
                        "設定変更",
                        "再起動後に反映されます。",
                    )
                refresh_pack_list(name)
            except Exception as error:
                QMessageBox.critical(
                    dialog,
                    "保存エラー",
                    str(error),
                )

        save_btn.clicked.connect(save_current)

        def create_pack():
            name, ok = QInputDialog.getText(
                dialog,
                "新規パック",
                "パック名（英数字と_-のみ）:",
            )
            if not ok or not name:
                return
            try:
                name = validate_pack_name(name)
                schema = blank_schema()
                save_user_pack(
                    name,
                    schema,
                    blank_adapter(),
                    {
                        "facets": [],
                        "GCOL": schema["GCOL"].copy(),
                    },
                )
                refresh_pack_list(name)
            except Exception as error:
                QMessageBox.critical(
                    dialog,
                    "作成エラー",
                    str(error),
                )

        def duplicate_selected():
            item = pack_list.currentItem()
            if not item:
                return
            source = item.text()
            name, ok = QInputDialog.getText(
                dialog,
                "パック複製",
                f"'{source}' のコピー名（英数字と_-のみ）:",
            )
            if not ok or not name:
                return
            try:
                destination = duplicate_pack(source, name)
                refresh_pack_list(destination.name)
            except Exception as error:
                QMessageBox.critical(
                    dialog,
                    "複製エラー",
                    str(error),
                )

        def delete_selected():
            item = pack_list.currentItem()
            if not item:
                return
            name = item.text()
            if name in registry:
                QMessageBox.warning(
                    dialog,
                    "エラー",
                    "組み込みパックは削除できません。",
                )
                return
            if (
                QMessageBox.question(
                    dialog,
                    "削除確認",
                    f"パック '{name}' を削除しますか？",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            try:
                delete_user_pack(name)
                refresh_pack_list()
            except Exception as error:
                QMessageBox.critical(
                    dialog,
                    "削除エラー",
                    str(error),
                )

        new_btn.clicked.connect(create_pack)
        dup_btn.clicked.connect(duplicate_selected)
        del_btn.clicked.connect(delete_selected)

        refresh_pack_list()
        dialog.exec()

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


class RawDataPreviewWidget(QWidget):
    def __init__(self, row, records_csv, parent=None):
        super().__init__(parent)
        self.row = row
        self.records_csv = records_csv
        self.wave_config = WAVEFORM or {}
        self.modes = waveform_modes(self.wave_config)
        self.mode_id = self.wave_config.get("default_mode") or self.modes[0].get("id", "all")
        self.base_enabled = False
        self.axis_open = False
        self.axis_settings = {}
        self.axis_inputs = {}
        self.mode_buttons = {}
        self.current_signal = None
        self.current_path = None
        self.steps_by_run = {}
        if self.wave_config.get("step_markers", False) and feature_enabled("steps"):
            try:
                self.steps_by_run, _fields, _mtime = load_steps_table(records_csv)
            except Exception:
                self.steps_by_run = {}
        self.files = [
            resolve_record_file_path(path, records_csv)
            for path in split_paths(row.get("raw_path", ""))
        ]

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        if not self.files:
            message = QLabel(
                "raw_path にCSVが登録されていません。実験記録を編集してCSVを追加すると、ここに表とグラフが表示されます。"
            )
            message.setWordWrap(True)
            message.setStyleSheet("color: #667085;")
            root.addWidget(message)
            root.addStretch()
            return

        top = QHBoxLayout()
        top.addWidget(QLabel("CSV"))
        self.file_combo = QComboBox()
        for path in self.files:
            self.file_combo.addItem(path.name, str(path))
        self.file_combo.currentIndexChanged.connect(self.load_selected_file)
        self.open_button = QPushButton("開く")
        self.open_button.clicked.connect(self.open_selected_file)
        top.addWidget(self.file_combo, stretch=1)
        top.addWidget(self.open_button)
        root.addLayout(top)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #667085;")
        root.addWidget(self.status_label)

        self.controls_widget = QWidget()
        self.controls_layout = QVBoxLayout(self.controls_widget)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(6)
        self.build_wave_controls()
        root.addWidget(self.controls_widget)

        self.plot = SignalPlotWidget()
        root.addWidget(self.plot)

        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setShowGrid(True)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setMinimumHeight(170)
        self.preview_table.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #D0D7DE;
                alternate-background-color: #F6F8FA;
            }
            QHeaderView::section {
                background: #EEF2F6;
                border: 1px solid #D0D7DE;
                padding: 5px;
                font-weight: 600;
            }
            """
        )
        root.addWidget(self.preview_table, stretch=1)

        self.load_selected_file()

    def build_wave_controls(self):
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        if len(self.modes) > 1:
            top.addWidget(QLabel("表示"))
            for mode in self.modes:
                button = QPushButton(mode.get("label", mode.get("id", "all")))
                button.setCheckable(True)
                button.setChecked(mode.get("id", "all") == self.mode_id)
                button.clicked.connect(
                    lambda _checked=False, mode_id=mode.get("id", "all"): self.set_mode(mode_id)
                )
                self.mode_buttons[mode.get("id", "all")] = button
                top.addWidget(button)
        if feature_enabled("baseline"):
            self.base_button = QPushButton("基準補正")
            self.base_button.setCheckable(True)
            self.base_button.clicked.connect(self.toggle_base)
            top.addWidget(self.base_button)
        self.axis_button = QPushButton("軸設定 ▸")
        self.axis_button.clicked.connect(self.toggle_axis_panel)
        top.addWidget(self.axis_button)
        top.addStretch()
        self.controls_layout.addLayout(top)

        self.axis_panel = QWidget()
        axis_layout = QVBoxLayout(self.axis_panel)
        axis_layout.setContentsMargins(0, 0, 0, 0)
        axis_layout.setSpacing(4)
        for items in (
            [("xmin", "X最小"), ("xmax", "X最大"), ("xstep", "X刻み")],
            [("ymin", "Y最小"), ("ymax", "Y最大"), ("ystep", "Y刻み")],
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            for key, label in items:
                row.addWidget(QLabel(label))
                editor = QLineEdit()
                editor.setFixedWidth(72)
                self.axis_inputs[key] = editor
                row.addWidget(editor)
            row.addStretch()
            axis_layout.addLayout(row)
        buttons = QHBoxLayout()
        apply_button = QPushButton("適用")
        auto_button = QPushButton("自動")
        apply_button.clicked.connect(self.apply_axis_settings)
        auto_button.clicked.connect(self.clear_axis_settings)
        buttons.addWidget(apply_button)
        buttons.addWidget(auto_button)
        hint = QLabel("空欄は自動。刻みは正の数だけ有効です。")
        hint.setStyleSheet("color: #667085;")
        buttons.addWidget(hint)
        buttons.addStretch()
        axis_layout.addLayout(buttons)
        self.axis_panel.setVisible(False)
        self.controls_layout.addWidget(self.axis_panel)

    def selected_path(self):
        if not hasattr(self, "file_combo"):
            return None
        value = self.file_combo.currentData()
        return Path(value) if value else None

    def open_selected_file(self):
        path = self.selected_path()
        if path is None or not path.exists():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def set_mode(self, mode_id):
        self.mode_id = mode_id
        for key, button in self.mode_buttons.items():
            button.setChecked(key == mode_id)
        self.load_selected_file()

    def toggle_base(self):
        self.base_enabled = bool(self.base_button.isChecked())
        self.redraw_current_signal()

    def toggle_axis_panel(self):
        self.axis_open = not self.axis_open
        self.axis_panel.setVisible(self.axis_open)
        self.axis_button.setText("軸設定 ▾" if self.axis_open else "軸設定 ▸")

    def apply_axis_settings(self):
        self.axis_settings = {
            key: editor.text().strip()
            for key, editor in self.axis_inputs.items()
        }
        self.redraw_current_signal()

    def clear_axis_settings(self):
        self.axis_settings = {}
        for editor in self.axis_inputs.values():
            editor.clear()
        self.redraw_current_signal()

    def redraw_current_signal(self):
        if self.current_signal is None:
            return
        self.plot.set_signal(
            self.current_signal,
            mode_config=waveform_mode(self.wave_config, self.mode_id),
            base=self.base_enabled,
            row=self.row,
            steps=self.steps_by_run.get(self.row.get("run_id", ""), []),
            axis_settings=self.axis_settings,
        )

    def load_selected_file(self):
        path = self.selected_path()
        self.current_path = path
        self.current_signal = None
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)
        self.plot.set_signal(None)
        if path is None:
            self.status_label.setText("CSVが選択されていません。")
            self.open_button.setEnabled(False)
            return
        if not path.exists():
            self.status_label.setText(f"CSVが見つかりません: {path}")
            self.open_button.setEnabled(False)
            return
        self.open_button.setEnabled(True)

        try:
            preview = load_csv_preview(path)
            self.populate_csv_table(preview)
            table_message = (
                f"{path.name}  |  {preview.total_rows} 行中 "
                f"{len(preview.rows)} 行を表示  |  encoding={preview.encoding}"
            )
        except Exception as error:
            preview = None
            table_message = f"CSV表プレビューを作れませんでした: {error}"

        if not MPL_AVAILABLE:
            self.plot.set_message(
                "高品質グラフ表示には matplotlib が必要です。"
            )
            graph_message = "グラフ: matplotlib が未インストールです"
        else:
            try:
                signal = active_pack().parse(path)
                self.current_signal = signal
                self.redraw_current_signal()
                channels = ", ".join(channel.name for channel in signal.channels[:4])
                graph_message = f"グラフ: {signal.x.name} を横軸に {channels} を表示"
            except Exception as error:
                self.plot.set_message(
                    "このCSVは現在のパックのグラフ設定では読み込めません。表プレビューで中身を確認できます。"
                )
                graph_message = f"グラフ: 読み込み不可 ({error})"

        self.status_label.setText(f"{table_message}\n{graph_message}")

    def populate_csv_table(self, preview):
        self.preview_table.setColumnCount(len(preview.header))
        self.preview_table.setRowCount(len(preview.rows))
        self.preview_table.setHorizontalHeaderLabels(preview.header)
        for row_index, row in enumerate(preview.rows):
            for column_index, value in enumerate(row[: len(preview.header)]):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.preview_table.setItem(row_index, column_index, item)
        header = self.preview_table.horizontalHeader()
        for column_index in range(len(preview.header)):
            header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Interactive)
            self.preview_table.setColumnWidth(column_index, 120)


class SignalPlotWidget(QWidget):
    MAX_POINTS = 8000
    SPAN_COLORS = ["#378ADD", "#1D9E75", "#BA7517", "#9B6DD6", "#C2543A"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.click_spm = None
        self.click_offset = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if not MPL_AVAILABLE:
            self.message_label = QLabel(
                "高品質グラフ表示には matplotlib が必要です。\n"
                "次のコマンドで追加できます: python -m pip install matplotlib"
            )
            self.message_label.setWordWrap(True)
            self.message_label.setStyleSheet(
                "color: #667085; padding: 16px; border: 1px solid #D0D7DE; "
                "border-radius: 8px; background: #FFFFFF;"
            )
            layout.addWidget(self.message_label)
            return

        self.figure = Figure(figsize=(6.6, 3.0), dpi=110)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(self.canvas)
        layout.addWidget(self.toolbar)
        self.click_label = QLabel("")
        self.click_label.setStyleSheet("color: #667085; font-size: 11px;")
        layout.addWidget(self.click_label)
        self.canvas.mpl_connect("button_press_event", self.on_plot_clicked)
        self.set_message("CSVを選択すると、ここにmatplotlibグラフが表示されます。")

    def set_signal(
        self,
        signal,
        mode_config=None,
        base=False,
        row=None,
        steps=None,
        axis_settings=None,
    ):
        if not MPL_AVAILABLE:
            return
        if signal is None:
            self.set_message("CSVを選択すると、ここにmatplotlibグラフが表示されます。")
            return
        self.draw_signal(
            signal,
            mode_config=mode_config,
            base=base,
            row=row or {},
            steps=steps or [],
            axis_settings=axis_settings or {},
        )

    def set_message(self, message):
        if not MPL_AVAILABLE:
            if hasattr(self, "message_label"):
                self.message_label.setText(message)
            return
        self.click_spm = None
        self.click_offset = None
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.axis("off")
        axis.text(
            0.02,
            0.92,
            message,
            transform=axis.transAxes,
            va="top",
            ha="left",
            color="#667085",
            wrap=True,
        )
        if hasattr(self, "click_label"):
            self.click_label.setText("")
        self.canvas.draw_idle()

    def draw_signal(self, signal, mode_config=None, base=False, row=None,
                    steps=None, axis_settings=None):
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        mode_config = mode_config or {
            "id": "all",
            "label": "Channels",
            "y_label": "Value",
            "channels": "all",
        }
        row = row or {}
        steps = steps or []
        axis_settings = axis_settings or {}
        x_values = list(signal.x.values)
        channel_names = waveform_channels(signal, mode_config)
        all_channels = {
            channel.name: channel for channel in signal.channels
        }
        channels = [
            all_channels[name] for name in channel_names
            if name in all_channels and all_channels[name].values
        ]
        if not x_values or not channels:
            self.set_message("グラフにできる数値データがありません。")
            return

        min_len = min([len(x_values), *(len(channel.values) for channel in channels)])
        if min_len < 2:
            self.set_message("グラフにできる数値データが足りません。")
            return

        x_values = x_values[:min_len]
        spm = signal.meta.get("samples_per_min")
        offset = signal.meta.get("row_offset", 2)
        self.click_spm = spm
        self.click_offset = offset
        if spm is not None:
            self.click_label.setText(
                "グラフをクリックすると、対応するCSV行番号をクリップボードへコピーします。"
            )
        else:
            self.click_label.setText("")

        base_offsets = {channel.name: 0.0 for channel in channels}
        t_base = None
        if base and spm is not None:
            base_row = fnum(row.get("base_row", ""))
            t_base = (
                (base_row - offset) / spm
                if base_row is not None else x_values[0]
            )
            base_index = min(
                range(len(x_values)),
                key=lambda index: abs(x_values[index] - t_base),
            )
            for channel in channels:
                base_offsets[channel.name] = channel.values[base_index]
            if base_row is not None:
                axis.set_title(
                    f"基準: 行{int(base_row)}",
                    fontsize=8,
                    loc="left",
                    color="#667085",
                )
            else:
                axis.set_title(
                    "基準: 先頭サンプル",
                    fontsize=8,
                    loc="left",
                    color="#667085",
                )

        step = max(1, min_len // self.MAX_POINTS)
        x_sample = x_values[:min_len:step]
        for channel in channels:
            y_values = [
                value - base_offsets[channel.name]
                for value in channel.values[:min_len]
            ]
            y_sample = y_values[::step]
            label = channel.name
            if channel.unit:
                label += f" [{channel.unit}]"
            if base:
                label += "-base"
            axis.plot(
                x_sample,
                y_sample,
                linewidth=1.4,
                marker=".",
                markersize=2.5,
                label=label,
            )

        x_unit = f" [{signal.x.unit}]" if signal.x.unit else ""
        axis.set_xlabel(f"{signal.x.name.capitalize()}{x_unit}")
        y_label = mode_config.get("y_label", "Value")
        selected_units = {channel.unit for channel in channels if channel.unit}
        if (
            mode_config.get("channels") == "all"
            and y_label == "Value"
            and len(selected_units) == 1
        ):
            y_label = f"Value [{next(iter(selected_units))}]"
        axis.set_ylabel(y_label)
        axis.grid(True, alpha=0.35)

        self.apply_axis_settings(axis, axis_settings)
        if t_base is not None:
            axis.axvline(t_base, color="#777", lw=0.9, ls=":")
        self.draw_step_markers(axis, steps, spm, offset)

        axis.legend(
            fontsize=8,
            loc="lower right",
            bbox_to_anchor=(1.0, 1.0),
            ncol=2,
            frameon=False,
            borderaxespad=0,
        )
        if step > 1:
            axis.set_title(
                f"{min_len:,} points shown with downsampling every {step} points",
                fontsize=9,
                color="#667085",
                loc="right",
            )
        self.figure.tight_layout()
        self.figure.subplots_adjust(top=0.86)
        self.canvas.draw_idle()

    def apply_axis_settings(self, axis, settings):
        def axis_value(key):
            return fnum(settings.get(key, ""))

        if axis_value("xmin") is not None or axis_value("xmax") is not None:
            axis.set_xlim(left=axis_value("xmin"), right=axis_value("xmax"))
        if axis_value("ymin") is not None or axis_value("ymax") is not None:
            axis.set_ylim(bottom=axis_value("ymin"), top=axis_value("ymax"))
        x_step = axis_value("xstep")
        y_step = axis_value("ystep")
        if x_step is not None and x_step > 0:
            axis.xaxis.set_major_locator(MultipleLocator(x_step))
        if y_step is not None and y_step > 0:
            axis.yaxis.set_major_locator(MultipleLocator(y_step))

    def draw_step_markers(self, axis, steps, spm, offset):
        if not steps:
            return
        has_rows = any(
            fnum(step.get("data_start_row", "")) is not None
            for step in steps
        )
        if has_rows and spm is not None:
            for index, step in enumerate(steps):
                start_row = fnum(step.get("data_start_row", ""))
                if start_row is None:
                    continue
                end_row = fnum(step.get("data_end_row", ""))
                start_x = (start_row - offset) / spm
                label = (
                    f"{step.get('step_no', '')} {step.get('action', '')} "
                    f"{step.get('liquid', '')}"
                ).strip()
                color = self.SPAN_COLORS[index % len(self.SPAN_COLORS)]
                if end_row is not None:
                    end_x = (end_row - offset) / spm
                    axis.axvspan(start_x, end_x, color=color, alpha=0.10)
                axis.axvline(start_x, ls="--", lw=0.9, color=color, alpha=0.9)
                axis.text(
                    start_x,
                    axis.get_ylim()[1],
                    label,
                    fontsize=7,
                    rotation=90,
                    va="top",
                    ha="right",
                    color=color,
                )
            return

        total = 0.0
        for step in steps:
            duration = fnum(step.get("duration_min", ""))
            label = (
                f"{step.get('step_no', '')} {step.get('action', '')} "
                f"{step.get('liquid', '')}"
            ).strip()
            axis.axvline(total, ls="--", lw=0.9, color="#BA7517", alpha=0.8)
            axis.text(
                total,
                axis.get_ylim()[1],
                label,
                fontsize=7,
                rotation=90,
                va="top",
                ha="right",
                color="#854F0B",
            )
            if duration is None:
                break
            total += duration

    def on_plot_clicked(self, event):
        if self.click_spm is None or self.click_offset is None:
            return
        if event.xdata is None or getattr(event, "button", 1) != 1:
            return
        toolbar_mode = getattr(self.toolbar, "mode", "")
        if toolbar_mode:
            return
        row_number = max(
            int(self.click_offset),
            int(round(event.xdata * self.click_spm)) + int(self.click_offset),
        )
        QApplication.clipboard().setText(str(row_number))
        self.click_label.setText(
            f"x={event.xdata:.3g} -> CSV行 {row_number} をコピーしました。"
        )


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
        self.list_widget.setHorizontalHeaderLabels(["ファイル名", "パス", "状態"])
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
        add_button = QPushButton("ファイルを追加")
        remove_button = QPushButton("選択した項目を削除")
        self.open_selected_button = QPushButton("選択したファイルを開く")
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
            status_item = QTableWidgetItem("存在します" if exists else "見つかりません")
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
        selected, _ = QFileDialog.getOpenFileNames(self, "ファイルを追加")
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
                "ファイルが見つかりません",
                f"ファイルが見つかりません。\n{resolved}",
            )
            self.update_open_button()
            return
        url = QUrl.fromLocalFile(str(resolved))
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                "ファイルを開けません",
                f"ファイルを開けませんでした。\n{resolved}",
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


def run(argv=None):
    app = QApplication(list(argv) if argv is not None else sys.argv)
    window = EvidexQtWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
