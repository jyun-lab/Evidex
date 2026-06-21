"""Filter and search logic for the Qt main window."""

import json

from PySide6.QtWidgets import QInputDialog, QMessageBox

from evidex.core.fields import ACTION_CHOICES
from evidex.core.filtering import fnum, row_matches
from evidex.core.i18n import t


class FilterMixin:
    """Methods for search, filter, and preset management."""

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
        self.adv_toggle_button.setText(t("btn.adv_filter", n=suffix, arrow=arrow))
        # 状態バー
        parts = []
        if f["grades"]:
            parts.append(f"Grade: {','.join(f['grades'])}")
        if f["vmin"] is not None or f["vmax"] is not None:
            lo = f["vmin"] if f["vmin"] is not None else "..."
            hi = f["vmax"] if f["vmax"] is not None else "..."
            parts.append(t("qt.filter.viscosity_range", lo=lo, hi=hi))
        if f["dfrom"] or f["dto"]:
            parts.append(t("qt.filter.date_range", start=f["dfrom"] or "...", end=f["dto"] or "..."))
        for key, label in (("series", t("menu.series")), ("chip", t("pane.field.chip")),
                           ("status", t("nav.section.status")), ("who", t("series.field.experimenter")),
                           ("understanding", t("pane.field.understanding")), ("action", t("steps.col.action")),
                           ("liquid", t("steps.col.liquid"))):
            if f.get(key):
                parts.append(f"{label}: {f[key]}")
        if f["has_raw"]:
            parts.append(t("search.filter.has_raw"))
        if f["no_steps"]:
            parts.append(t("main.label.no_steps"))
        if f["unread"]:
            parts.append(t("main.label.unread_only"))
        if parts:
            self.filter_status_bar.setText(t("qt.common.filters") + " | ".join(parts))
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
        self.adv_toggle_button.setText(t("btn.adv_filter", n=suffix, arrow=arrow))

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

    def _on_preset_selected(self, name):
        if not name:
            return
        st = self._load_prefs().get("presets", {}).get(name)
        if st:
            self._apply_filter_state(st)

    def save_preset(self):
        name, ok = QInputDialog.getText(
            self, t("qt.common.save_preset"), t("prefs.msg.preset_name"))
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
            QMessageBox.warning(self, t("data.msg.save_error"), str(e))
            return False
