"""Field editing tab logic for the tkinter schema editor."""

import tkinter as tk
from tkinter import messagebox, ttk

from evidex.core.i18n import t
from evidex.core.pack_ops import _PACK_NAME_RE
from evidex.core.table_style import configure_treeview_rows, stripe_tag


class TkSchemaFieldsMixin:
    """フィールド編集タブの UI 構築とロジック。"""

    def _build_fields_tab(self):
        """タブ1: フィールド編集。"""
        self._field_intro = ttk.Label(
            self._tab_fields,
            text=t("schema_editor.fields_intro"),
            justify="left",
            foreground="#555",
        )
        self._field_intro.pack(fill="x", pady=(0, 8))
        self._make_responsive_wrap(
            self._field_intro, self._tab_fields
        )

        self._field_pw = ttk.PanedWindow(self._tab_fields, orient="horizontal")
        self._field_pw.pack(fill="both", expand=True)
        field_left = ttk.Frame(self._field_pw)
        field_right = ttk.LabelFrame(self._field_pw, text=t("schema_editor.str10"), padding=10)
        self._field_pw.add(field_left, weight=2)
        self._field_pw.add(field_right, weight=1)

        self._field_tree = ttk.Treeview(
            field_left, columns=("id", "jp", "en", "type", "choices"), show="headings"
        )
        configure_treeview_rows(self._field_tree)
        headings = {
            "id": t("schema_editor.field_id_short"),
            "jp": t("schema_editor.str8"),
            "en": t("schema_editor.english"),
            "type": t("schema_editor.input_method"),
            "choices": t("schema_editor.choices"),
        }
        widths = {"id": 110, "jp": 130, "en": 130, "type": 70, "choices": 170}
        for column in self._field_tree["columns"]:
            self._field_tree.heading(column, text=headings[column])
            self._field_tree.column(
                column, width=widths[column], minwidth=60, anchor="w", stretch=False
            )

        # Reserve list actions and the horizontal scrollbar at the bottom first.
        field_buttons = ttk.Frame(field_left)
        field_buttons.pack(side="bottom", fill="x", pady=(4, 0))
        self._field_hscroll = ttk.Scrollbar(
            field_left, orient="horizontal", command=self._field_tree.xview
        )
        self._field_hscroll.pack(side="bottom", fill="x")
        self._field_tree.configure(xscrollcommand=self._field_hscroll.set)
        self._field_tree.pack(fill="both", expand=True)

        self._field_id = tk.StringVar()
        self._field_jp = tk.StringVar()
        self._field_en = tk.StringVar()
        self._type_labels = {
            "text": t("schema_editor.type_text"),
            "number": t("schema_editor.type_number"),
            "date": t("schema_editor.type_date"),
            "choice": t("schema_editor.type_choice"),
        }
        self._type_ids = {label: kind for kind, label in self._type_labels.items()}
        self._field_type = tk.StringVar(value=self._type_labels["text"])
        self._field_choices = tk.StringVar()
        self._field_type_help = tk.StringVar()

        editor_help = ttk.Label(
            field_right,
            text=t("schema_editor.field_editor_help"),
            justify="left",
            foreground="#555",
        )
        editor_help.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._make_responsive_wrap(
            editor_help, field_right, margin=20, minimum=120
        )

        for row, (label, variable) in enumerate((
            (t("schema_editor.field_id"), self._field_id),
            (t("schema_editor.str11"), self._field_jp),
            (t("schema_editor.str12"), self._field_en),
        ), start=1):
            grid_row = row * 2 - 1
            ttk.Label(field_right, text=label).grid(
                row=grid_row, column=0, sticky="w"
            )
            ttk.Entry(field_right, textvariable=variable).grid(
                row=grid_row + 1, column=0, sticky="ew", pady=(0, 8)
            )
        ttk.Label(field_right, text=t("schema_editor.input_method")).grid(
            row=7, column=0, sticky="w"
        )
        self._field_type_box = ttk.Combobox(
            field_right,
            textvariable=self._field_type,
            values=list(self._type_labels.values()),
            state="readonly",
        )
        self._field_type_box.grid(row=8, column=0, sticky="ew")
        self._field_type_help_label = ttk.Label(
            field_right,
            textvariable=self._field_type_help,
            justify="left",
            foreground="#666",
        )
        self._field_type_help_label.grid(row=9, column=0, sticky="ew", pady=(2, 8))
        self._make_responsive_wrap(
            self._field_type_help_label, field_right, margin=20, minimum=120
        )
        ttk.Label(field_right, text=t("schema_editor.str14")).grid(
            row=10, column=0, sticky="w"
        )
        self._field_choices_entry = ttk.Entry(
            field_right, textvariable=self._field_choices
        )
        self._field_choices_entry.grid(
            row=11, column=0, sticky="ew"
        )
        field_choices_help = ttk.Label(
            field_right,
            text=t("schema_editor.choices_help"),
            justify="left",
            foreground="#666",
        )
        field_choices_help.grid(
            row=12, column=0, sticky="ew", pady=(2, 8)
        )
        self._make_responsive_wrap(
            field_choices_help, field_right, margin=20, minimum=120
        )
        self._apply_field_button = ttk.Button(field_right, text=t("schema_editor.str15"))
        self._apply_field_button.grid(row=13, column=0, sticky="e")
        field_right.columnconfigure(0, weight=1)
        self._add_field_button = ttk.Button(
            field_buttons, text=t("schema_editor.add")
        )
        self._move_field_up_button = ttk.Button(
            field_buttons, text="▲"
        )
        self._move_field_down_button = ttk.Button(
            field_buttons, text="▼"
        )
        self._delete_field_button = ttk.Button(
            field_buttons, text=t("schema_editor.delete")
        )
        self._add_field_button.pack(side="left", padx=(0, 4))
        self._move_field_up_button.pack(side="left")
        self._move_field_down_button.pack(
            side="left", padx=(4, 0)
        )
        self._delete_field_button.pack(side="right")

    def _selected_field_kind(self):
        return self._type_ids.get(self._field_type.get(), "text")

    def _refresh_type_help(self, _event=None):
        kind = self._selected_field_kind()
        self._field_type_help.set(t(f"schema_editor.type_{kind}_help"))
        self._field_choices_entry.configure(
            state="normal" if kind == "choice" else "disabled"
        )

    def _field_kind(self, field):
        if field in self._schema.get("CHOICES", {}):
            return "choice"
        return self._schema.get("FIELD_TYPES", {}).get(field, "text")

    def _reload_field_tree(self, select_index=None):
        self._field_tree.delete(*self._field_tree.get_children())
        schema = self._schema
        for index, field in enumerate(schema.get("RUN_FIELDS", [])):
            choices = schema.get("CHOICES", {}).get(field, [])
            self._field_tree.insert(
                "",
                "end",
                tags=(stripe_tag(index),),
                values=(
                    field,
                    schema.get("JP_LABEL", {}).get(field, ""),
                    schema.get("LABEL_EN", {}).get(field, ""),
                    self._type_labels.get(
                        self._field_kind(field), self._field_kind(field)
                    ),
                    ", ".join(choices),
                ),
            )
        children = self._field_tree.get_children()
        if children and select_index is not None:
            index = max(0, min(select_index, len(children) - 1))
            self._field_tree.selection_set(children[index])
            self._field_tree.focus(children[index])
            self._field_tree.see(children[index])
            self._on_field_select()
        self._reload_facets()

    def _selected_field_index(self):
        selected = self._field_tree.selection()
        return self._field_tree.index(selected[0]) if selected else None

    def _on_field_select(self, _event=None):
        index = self._selected_field_index()
        if index is None:
            return
        schema = self._schema
        field = schema["RUN_FIELDS"][index]
        self._field_id.set(field)
        self._field_jp.set(schema.get("JP_LABEL", {}).get(field, ""))
        self._field_en.set(schema.get("LABEL_EN", {}).get(field, ""))
        self._field_type.set(self._type_labels.get(
            self._field_kind(field), self._type_labels["text"]
        ))
        self._field_choices.set(",".join(schema.get("CHOICES", {}).get(field, [])))
        self._refresh_type_help()

    def _apply_field_edit(self):
        index = self._selected_field_index()
        if index is None or self._builtin:
            return
        schema = self._schema
        old_id = schema["RUN_FIELDS"][index]
        new_id = self._field_id.get().strip()
        if not new_id or not _PACK_NAME_RE.fullmatch(new_id):
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.invalid_field_id"),
                parent=self,
            )
            return
        if new_id != old_id and new_id in schema["RUN_FIELDS"]:
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.duplicate_field"),
                parent=self,
            )
            return

        schema["RUN_FIELDS"][index] = new_id
        for key in ("JP_LABEL", "LABEL_EN", "FIELD_TYPES", "CHOICES"):
            schema.setdefault(key, {})
        schema["JP_LABEL"][new_id] = self._field_jp.get().strip()
        schema["LABEL_EN"][new_id] = self._field_en.get().strip()
        kind = self._selected_field_kind()
        schema["FIELD_TYPES"][new_id] = kind
        if kind == "choice":
            schema["CHOICES"][new_id] = [
                value.strip() for value in self._field_choices.get().split(",") if value.strip()
            ]
        else:
            schema["CHOICES"].pop(new_id, None)
        if old_id != new_id:
            for key in ("JP_LABEL", "LABEL_EN", "FIELD_TYPES", "CHOICES"):
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
        self._reload_field_tree(index)

    def _add_field(self):
        if self._builtin:
            return
        schema = self._schema
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
        self._reload_field_tree(len(schema["RUN_FIELDS"]) - 1)

    def _delete_field(self):
        index = self._selected_field_index()
        if index is None or self._builtin:
            return
        schema = self._schema
        field = schema["RUN_FIELDS"][index]
        if field == "run_id":
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.run_id_required"),
                parent=self,
            )
            return
        schema["RUN_FIELDS"].pop(index)
        for key in ("JP_LABEL", "LABEL_EN", "FIELD_TYPES", "CHOICES"):
            schema.setdefault(key, {}).pop(field, None)
        schema["COLS"] = [item for item in schema.get("COLS", []) if item[0] != field]
        schema.get("HEAD", {}).pop(field, None)
        schema["facets"] = [
            facet for facet in schema.get("facets", []) if facet.get("field") != field
        ]
        self._reload_field_tree(index)

    def _move_field(self, delta):
        index = self._selected_field_index()
        if index is None or self._builtin:
            return
        fields = self._schema["RUN_FIELDS"]
        target = index + delta
        if target < 0 or target >= len(fields):
            return
        fields[index], fields[target] = fields[target], fields[index]
        self._reload_field_tree(target)
