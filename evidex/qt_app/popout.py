from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from evidex.core.fields import GCOL, feature_enabled

from .theme import _DARK, _LIGHT
from evidex.core.i18n import t


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
        self.setWindowTitle(t("qt.popout.title"))
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

        self.prev_button = QPushButton(t("btn.prev"))
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

        self.next_button = QPushButton(t("btn.next"))
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
        self.edit_button = QPushButton(t("btn.edit_run"))
        self.edit_button.setStyleSheet(_popout_action_btn_ss(parent.dark))
        self.edit_button.clicked.connect(self.edit_current)
        footer.addWidget(self.edit_button)
        if self.owner.steps_enabled:
            self.steps_button = QPushButton(t("main.menu.edit_steps"))
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

        run_id = row.get("run_id", "") or t("qt.common.no_id")
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
        self.tabs.addTab(self.owner.build_basic_tab(row), t("pane.tab.basic"))
        if self.owner.steps_enabled:
            self.tabs.addTab(self.owner.build_steps_tab(row), t("pane.tab.steps"))
        self.tabs.addTab(self.owner.build_files_tab(row), t("menu.file"))
        if self.owner.series_enabled:
            self.tabs.addTab(self.owner.build_series_tab(row), t("pane.tab.series"))

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
