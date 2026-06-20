"""Navigation panel for the Qt main window."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTextEdit,
)

from evidex.core.fields import CHOICES, FACETS, get_label
from evidex.core.filtering import norm, row_matches
from evidex.core.i18n import t


class NavigationMixin:
    """Methods for the left navigation panel."""

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
