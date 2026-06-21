"""Detail pane rendering for the Qt main window."""

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from evidex.core.fields import (
    GCOL,
    LONG_FIELDS,
    STEP_FORM,
    feature_enabled,
)
from evidex.core.filtering import fnum
from evidex.core.icons import icon_for_action
from evidex.core.media import is_image_path
from evidex.core.record_table import record_basic_items, record_file_entries

from .waveform import RawDataPreviewWidget
from evidex.core.i18n import t


class DetailMixin:
    """Methods for building the detail pane tabs."""

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
            self.empty_tab(t("qt.detail.select_record_prompt")),
            t("pane.tab.basic"),
        )
        self.detail_tabs.addTab(
            self.empty_tab(t("qt.detail.files_prompt")),
            t("menu.file"),
        )
        self.detail_tabs.addTab(
            self.empty_tab(t("qt.detail.raw_data_prompt")),
            t("qt.detail.csv_graph"),
        )
        self.current_row = None
        self.edit_button.setEnabled(False)
        self.steps_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.popout_button.setEnabled(False)
        self.detail_title.setText(t("qt.detail.select_record"))

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
        self.detail_tabs.addTab(self.build_basic_tab(row), t("pane.tab.basic"))
        if self.steps_enabled:
            self.detail_tabs.addTab(self.build_steps_tab(row), t("pane.tab.steps"))
        self.detail_tabs.addTab(self.build_files_tab(row), t("menu.file"))
        self.detail_tabs.addTab(self.build_raw_data_tab(row), t("qt.detail.csv_graph"))
        if self.series_enabled:
            self.detail_tabs.addTab(self.build_series_tab(row), t("pane.tab.series"))

    def build_basic_tab(self, row):
        area, layout = self.make_scroll_page()
        title = row.get("run_id", "") or t("qt.common.no_id")
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
            empty = QLabel(t("pane.msg.no_steps"))
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
            empty = QLabel(t("pane.msg.no_series"))
            empty.setStyleSheet(self._muted_ss())
            layout.addWidget(empty)
            layout.addStretch()
            return area

        runs = [r for r in self.record_table.rows
                if (r.get("series_id", "") or "").strip() == sid]
        runs.sort(key=lambda x: (x.get("date", ""), x.get("run_id", "")))

        # 概要ヘッダ
        heading = QLabel(t("pane.label.series_title", sid=sid))
        heading.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {self._theme()['text']};")
        layout.addWidget(heading)

        dates = [x.get("date", "") for x in runs if x.get("date", "")]
        period = f"{min(dates)} 〜 {max(dates)}" if dates else "—"
        summary = QLabel(t("series.label.summary", n=len(runs), period=period))
        summary.setStyleSheet(self._muted_ss())
        layout.addWidget(summary)

        # Grade 推移
        if feature_enabled("grading"):
            grade_row = QHBoxLayout()
            grade_row.setSpacing(4)
            grade_label = QLabel(t("series.label.grade_seq"))
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
            ("objective", t("series.field.objective")),
            ("claim", t("series.field.claim")),
            ("established_knowns", t("series.field.established_knowns")),
            ("unresolved", t("series.field.unresolved")),
            ("my_assessment", t("series.field.my_assessment")),
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
            note = QLabel(t("qt.detail.series_unregistered"))
            note.setStyleSheet(self._muted_ss())
            note.setWordWrap(True)
            layout.addWidget(note)

        # 差分タイムライン
        tl_label = QLabel(t("pane.label.timeline"))
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
                    il = QLabel(t("pane.label.initial_condition") + "、".join(init_parts))
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
                    nl = QLabel(t("pane.msg.no_change"))
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
            empty = QLabel(t("qt.detail.no_files"))
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
            img_heading = QLabel(t("qt.detail.images_count", n=len(image_entries)))
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
                status = QLabel(t("qt.file.exists") if entry.exists else t("qt.file.missing"))
                status.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Preferred,
                )
                status.setStyleSheet(
                    "color: #166534; font-weight: 700;"
                    if entry.exists
                    else "color: #C2410C; font-weight: 700;"
                )
                open_button = QPushButton(t("btn.open"))
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
                t("qt.file.not_found_title"),
                t("pane.msg.file_not_found", path=entry.resolved_path),
            )
            return
        url = QUrl.fromLocalFile(str(entry.resolved_path))
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                t("qt.file.open_failed_title"),
                t("qt.file.open_failed", path=entry.resolved_path),
            )
