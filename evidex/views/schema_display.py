"""Display settings tab logic for the tkinter schema editor."""

import copy
import re
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk

from evidex.core.i18n import t


class TkSchemaDisplayMixin:
    """表示設定タブの UI 構築とロジック。"""

    def _build_display_tab(self):
        """タブ3: 表示設定。"""
        display_intro = ttk.Label(
            self._tab_display,
            text=t("schema_editor.display_intro"),
            justify="left",
            foreground="#555",
        )
        display_intro.pack(fill="x", pady=(0, 8))
        self._make_responsive_wrap(display_intro, self._tab_display)

        self._display_tabs = ttk.Notebook(self._tab_display)
        self._display_tabs.pack(fill="both", expand=True)
        facet_frame = ttk.Frame(self._display_tabs, padding=10)
        color_frame = ttk.Frame(self._display_tabs, padding=10)
        self._display_tabs.add(facet_frame, text=t("schema_editor.facets"))
        self._display_tabs.add(color_frame, text=t("schema_editor.features"))

        facet_help = ttk.Label(
            facet_frame,
            text=t("schema_editor.facets_help"),
            justify="left",
            foreground="#555",
        )
        facet_help.pack(fill="x", pady=(0, 8))
        self._make_responsive_wrap(facet_help, facet_frame, margin=20)

        self._facet_list = tk.Listbox(facet_frame, selectmode=tk.MULTIPLE, exportselection=False)
        self._facet_list.pack(fill="both", expand=True)

        self._color_vars = {grade: tk.StringVar() for grade in "ABC"}
        self._feature_vars = {
            name: tk.BooleanVar(value=False)
            for name in ("steps", "series", "grading", "baseline")
        }
        feature_intro = ttk.Label(
            color_frame,
            text=t("schema_editor.features_help"),
            justify="left",
            foreground="#555",
        )
        feature_intro.grid(
            row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8)
        )
        self._make_responsive_wrap(feature_intro, color_frame, margin=20)

        for row, name in enumerate(self._feature_vars, start=1):
            check = ttk.Checkbutton(
                color_frame,
                text=t(f"schema_editor.feature_{name}"),
                variable=self._feature_vars[name],
            )
            check.grid(row=row * 2 - 1, column=0, columnspan=3, sticky="w")
            description = ttk.Label(
                color_frame,
                text=t(f"schema_editor.feature_{name}_help"),
                justify="left",
                foreground="#666",
            )
            description.grid(
                row=row * 2, column=0, columnspan=3,
                sticky="ew", padx=(24, 0), pady=(0, 5)
            )
            self._make_responsive_wrap(
                description, color_frame, margin=44
            )

        ttk.Separator(color_frame).grid(
            row=9, column=0, columnspan=3, sticky="ew", pady=(8, 6)
        )
        grade_color_title = ttk.Label(
            color_frame, text=t("schema_editor.colors")
        )
        grade_color_title.grid(
            row=10, column=0, columnspan=3, sticky="w"
        )
        self._grade_color_widgets = [grade_color_title]
        for row, grade in enumerate("ABC", start=11):
            ttk.Label(color_frame, text=f"{grade}:").grid(row=row, column=0, sticky="w", pady=4)
            color_entry = ttk.Entry(
                color_frame, textvariable=self._color_vars[grade], width=12
            )
            color_entry.grid(
                row=row, column=1, sticky="ew", padx=(6, 4), pady=4
            )
            color_button = ttk.Button(
                color_frame,
                text=t("schema_editor.choose_color"),
                command=lambda value=grade: self._choose_color(value),
            )
            color_button.grid(row=row, column=2, pady=4)
            self._grade_color_widgets.extend((color_entry, color_button))
        color_frame.columnconfigure(1, weight=1)
        self._grade_color_buttons = {}
        for grade, widget in zip(
            "ABC", self._grade_color_widgets[2::2]
        ):
            self._grade_color_buttons[grade] = widget
        self._apply_display_button = ttk.Button(
            self._tab_display,
            text=t("schema_editor.apply_screen_settings"),
        )
        self._apply_display_button.pack(
            side="bottom", anchor="e", pady=(8, 0)
        )

    def _choose_color(self, grade):
        _rgb, color = colorchooser.askcolor(self._color_vars[grade].get(), parent=self)
        if color:
            self._color_vars[grade].set(color.upper())

    def _update_grade_color_state(self, *_):
        state_name = "normal" if self._feature_vars["grading"].get() else "disabled"
        for widget in self._grade_color_widgets[1:]:
            widget.configure(state=state_name)

    def _reload_facets(self):
        if not hasattr(self._facet_list, "delete"):
            return
        schema = self._schema
        enabled = {facet.get("field") for facet in schema.get("facets", [])}
        self._facet_list.delete(0, tk.END)
        for index, field in enumerate(schema.get("RUN_FIELDS", [])):
            label = (
                schema.get("JP_LABEL", {}).get(field)
                or schema.get("LABEL_EN", {}).get(field)
                or field
            )
            self._facet_list.insert(tk.END, f"{label}  ({field})")
            if field in enabled:
                self._facet_list.selection_set(index)

    def _apply_display_edit(self):
        schema = self._schema
        selected = set(self._facet_list.curselection())
        previous = {
            facet.get("field"): facet for facet in schema.get("facets", [])
        }
        facets = []
        for index, field in enumerate(schema.get("RUN_FIELDS", [])):
            if index not in selected:
                continue
            facets.append(
                previous.get(
                    field,
                    {
                        "field": field,
                        "label_key": "",
                        "source": "choices" if field in schema.get("CHOICES", {}) else "data",
                        "match": "exact",
                    },
                )
            )
        colors = {}
        features = {
            name: variable.get()
            for name, variable in self._feature_vars.items()
        }
        if features["grading"]:
            for grade in "ABC":
                value = self._color_vars[grade].get().strip()
                if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
                    messagebox.showerror(
                        t("schema_editor.error_title"),
                        t("schema_editor.invalid_color", grade=grade),
                        parent=self,
                    )
                    return False
                colors[grade] = value.upper()
        schema["facets"] = facets
        schema["GCOL"] = colors
        schema["features"] = features
        self._viz = {"facets": copy.deepcopy(facets), "GCOL": colors.copy()}
        return True
