"""Theme application logic for the Qt main window."""

from PySide6.QtGui import QColor

from .theme import _DARK, _LIGHT
from evidex.core.i18n import t


class ThemeMixin:
    """テーマ切り替えとスタイル適用。"""

    def _theme(self):
        """現在のテーマカラー辞書を返す"""
        return _DARK if self.dark else _LIGHT

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
