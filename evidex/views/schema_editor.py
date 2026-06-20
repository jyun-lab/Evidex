import copy
import json
import re
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from evidex.components import Tooltip
from evidex.core import config
from evidex.core.i18n import t
from evidex.core.pack_ops import (
    _PACK_NAME_RE,
    _REQUIRED_SCHEMA_KEYS,
    adapter_mapping_layout,
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
from evidex.core.schema import load_schema, pack_resource_dir
from evidex.core.table_style import configure_treeview_rows, stripe_tag
from evidex.packs import PackInterface, get_pack_names, registry

# Backward compatibility aliases for the old underscore-prefixed names
_blank_schema = blank_schema
_blank_adapter = blank_adapter


def open_schema_editor(parent):
    top = tk.Toplevel(parent)
    top.title(t("schema_editor.str1"))
    screen_w = max(640, top.winfo_screenwidth())
    screen_h = max(480, top.winfo_screenheight())
    width = min(screen_w, min(1100, max(680, screen_w - 40)))
    height = min(screen_h, min(720, max(500, screen_h - 80)))
    top.geometry(f"{width}x{height}")
    top.minsize(min(680, screen_w), min(500, screen_h))
    top.transient(parent)
    top.grab_set()

    state = {
        "schema": {},
        "adapter": {},
        "viz": {},
        "builtin": True,
        "python_adapter": False,
    }
    from evidex.core import settings

    current_pack = tk.StringVar(
        value=settings.get("active_pack", config.DEFAULT_PACK)
    )

    def make_responsive_wrap(label, container, margin=24, minimum=160):
        def update_wrap(event):
            label.configure(wraplength=max(minimum, event.width - margin))

        container.bind("<Configure>", update_wrap, add="+")

    def add_scrollable_tab(notebook_widget, label):
        page = ttk.Frame(notebook_widget)
        canvas = tk.Canvas(page, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(
            page, orient="vertical", command=canvas.yview
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        content = ttk.Frame(canvas, padding=10)
        content_window = canvas.create_window(
            (0, 0), window=content, anchor="nw"
        )

        def sync_content_size(_event=None):
            width = max(1, canvas.winfo_width())
            height = max(canvas.winfo_height(), content.winfo_reqheight())
            canvas.itemconfigure(
                content_window, width=width, height=height
            )
            canvas.configure(scrollregion=canvas.bbox("all"))

        canvas.bind("<Configure>", sync_content_size, add="+")
        content.bind(
            "<Configure>",
            lambda _event: canvas.after_idle(sync_content_size),
            add="+",
        )
        notebook_widget.add(page, text=label)
        return page, content, canvas, scrollbar

    def enable_page_mousewheel(container, canvas):
        def scroll_page(event):
            first, last = canvas.yview()
            if first == 0.0 and last == 1.0:
                return None
            steps = int(-event.delta / 120)
            canvas.yview_scroll(steps or (-1 if event.delta > 0 else 1), "units")
            return "break"

        def bind_widget(widget):
            if widget.winfo_class() not in {
                "Listbox", "Treeview", "Text", "TCombobox"
            }:
                widget.bind("<MouseWheel>", scroll_page, add="+")
            for child in widget.winfo_children():
                bind_widget(child)

        bind_widget(container)

    main_pw = ttk.PanedWindow(top, orient="horizontal")
    main_pw.pack(fill="both", expand=True, padx=10, pady=10)

    left = ttk.Frame(main_pw)
    main_pw.add(left, weight=1)
    ttk.Label(left, text=t("schema_editor.str2")).pack(anchor="w", pady=(0, 4))

    # Reserve the action bar at the bottom first so it remains visible on short screens.
    left_buttons = ttk.Frame(left)
    left_buttons.pack(side="bottom", fill="x", pady=(4, 0))
    for column in range(2):
        left_buttons.columnconfigure(column, weight=1)

    list_frame = ttk.Frame(left)
    list_frame.pack(fill="both", expand=True)
    pack_list = tk.Listbox(list_frame, exportselection=False)
    pack_list.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=pack_list.yview)
    scrollbar.pack(side="right", fill="y")
    pack_list.configure(yscrollcommand=scrollbar.set)

    right = ttk.Frame(main_pw)
    main_pw.add(right, weight=3)

    pack_selector_frame = ttk.Frame(right)
    pack_selector_frame.pack(fill="x", pady=(0, 4))
    ttk.Label(
        pack_selector_frame,
        text=t("schema_editor.pack_to_edit"),
    ).pack(side="left")
    pack_selector = ttk.Combobox(
        pack_selector_frame,
        textvariable=current_pack,
        state="readonly",
        width=24,
    )
    pack_selector.pack(side="left", padx=(6, 8))
    selected_pack_label = ttk.Label(pack_selector_frame, anchor="w")
    selected_pack_label.pack(side="left", fill="x", expand=True)

    # Reserve the save bar before the notebook so wide tab contents cannot hide it.
    bottom = ttk.Frame(right)
    bottom.pack(side="bottom", fill="x", pady=(8, 0))
    save_button = ttk.Button(bottom, text=t("schema_editor.str7"), state="disabled")
    save_button.pack(side="right", padx=(8, 0))
    readonly_label = ttk.Label(
        bottom, text=t("schema_editor.str6"), anchor="w", justify="left"
    )
    readonly_label.pack(side="left", fill="x", expand=True)
    make_responsive_wrap(readonly_label, bottom, margin=140)

    notebook = ttk.Notebook(right)
    notebook.pack(fill="both", expand=True)
    (
        tab_fields_page,
        tab_fields,
        fields_canvas,
        fields_scrollbar,
    ) = add_scrollable_tab(notebook, t("schema_editor.str3"))
    (
        tab_adapter_page,
        tab_adapter,
        adapter_canvas,
        adapter_scrollbar,
    ) = add_scrollable_tab(notebook, t("schema_editor.str4"))
    (
        tab_display_page,
        tab_display,
        display_canvas,
        display_scrollbar,
    ) = add_scrollable_tab(notebook, t("schema_editor.str5"))

    field_intro = ttk.Label(
        tab_fields,
        text=t("schema_editor.fields_intro"),
        justify="left",
        foreground="#555",
    )
    field_intro.pack(fill="x", pady=(0, 8))
    make_responsive_wrap(field_intro, tab_fields)

    field_pw = ttk.PanedWindow(tab_fields, orient="horizontal")
    field_pw.pack(fill="both", expand=True)
    field_left = ttk.Frame(field_pw)
    field_right = ttk.LabelFrame(field_pw, text=t("schema_editor.str10"), padding=10)
    field_pw.add(field_left, weight=2)
    field_pw.add(field_right, weight=1)

    field_tree = ttk.Treeview(
        field_left, columns=("id", "jp", "en", "type", "choices"), show="headings"
    )
    configure_treeview_rows(field_tree)
    headings = {
        "id": t("schema_editor.field_id_short"),
        "jp": t("schema_editor.str8"),
        "en": t("schema_editor.english"),
        "type": t("schema_editor.input_method"),
        "choices": t("schema_editor.choices"),
    }
    widths = {"id": 110, "jp": 130, "en": 130, "type": 70, "choices": 170}
    for column in field_tree["columns"]:
        field_tree.heading(column, text=headings[column])
        field_tree.column(
            column, width=widths[column], minwidth=60, anchor="w", stretch=False
        )

    # Reserve list actions and the horizontal scrollbar at the bottom first.
    field_buttons = ttk.Frame(field_left)
    field_buttons.pack(side="bottom", fill="x", pady=(4, 0))
    field_hscroll = ttk.Scrollbar(
        field_left, orient="horizontal", command=field_tree.xview
    )
    field_hscroll.pack(side="bottom", fill="x")
    field_tree.configure(xscrollcommand=field_hscroll.set)
    field_tree.pack(fill="both", expand=True)

    field_id = tk.StringVar()
    field_jp = tk.StringVar()
    field_en = tk.StringVar()
    type_labels = {
        "text": t("schema_editor.type_text"),
        "number": t("schema_editor.type_number"),
        "date": t("schema_editor.type_date"),
        "choice": t("schema_editor.type_choice"),
    }
    type_ids = {label: kind for kind, label in type_labels.items()}
    field_type = tk.StringVar(value=type_labels["text"])
    field_choices = tk.StringVar()
    field_type_help = tk.StringVar()

    editor_help = ttk.Label(
        field_right,
        text=t("schema_editor.field_editor_help"),
        justify="left",
        foreground="#555",
    )
    editor_help.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    make_responsive_wrap(editor_help, field_right, margin=20, minimum=120)

    for row, (label, variable) in enumerate((
        (t("schema_editor.field_id"), field_id),
        (t("schema_editor.str11"), field_jp),
        (t("schema_editor.str12"), field_en),
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
    field_type_box = ttk.Combobox(
        field_right,
        textvariable=field_type,
        values=list(type_labels.values()),
        state="readonly",
    )
    field_type_box.grid(row=8, column=0, sticky="ew")
    field_type_help_label = ttk.Label(
        field_right,
        textvariable=field_type_help,
        justify="left",
        foreground="#666",
    )
    field_type_help_label.grid(row=9, column=0, sticky="ew", pady=(2, 8))
    make_responsive_wrap(
        field_type_help_label, field_right, margin=20, minimum=120
    )
    ttk.Label(field_right, text=t("schema_editor.str14")).grid(
        row=10, column=0, sticky="w"
    )
    field_choices_entry = ttk.Entry(
        field_right, textvariable=field_choices
    )
    field_choices_entry.grid(
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
    make_responsive_wrap(
        field_choices_help, field_right, margin=20, minimum=120
    )
    apply_field_button = ttk.Button(field_right, text=t("schema_editor.str15"))
    apply_field_button.grid(row=13, column=0, sticky="e")
    field_right.columnconfigure(0, weight=1)

    def selected_field_kind():
        return type_ids.get(field_type.get(), "text")

    def refresh_type_help(_event=None):
        kind = selected_field_kind()
        field_type_help.set(t(f"schema_editor.type_{kind}_help"))
        field_choices_entry.configure(
            state="normal" if kind == "choice" else "disabled"
        )

    field_type_box.bind("<<ComboboxSelected>>", refresh_type_help)
    refresh_type_help()

    def field_kind(schema, field):
        if field in schema.get("CHOICES", {}):
            return "choice"
        return schema.get("FIELD_TYPES", {}).get(field, "text")

    def reload_field_tree(select_index=None):
        field_tree.delete(*field_tree.get_children())
        schema = state["schema"]
        for index, field in enumerate(schema.get("RUN_FIELDS", [])):
            choices = schema.get("CHOICES", {}).get(field, [])
            field_tree.insert(
                "",
                "end",
                tags=(stripe_tag(index),),
                values=(
                    field,
                    schema.get("JP_LABEL", {}).get(field, ""),
                    schema.get("LABEL_EN", {}).get(field, ""),
                    type_labels.get(
                        field_kind(schema, field), field_kind(schema, field)
                    ),
                    ", ".join(choices),
                ),
            )
        children = field_tree.get_children()
        if children and select_index is not None:
            index = max(0, min(select_index, len(children) - 1))
            field_tree.selection_set(children[index])
            field_tree.focus(children[index])
            field_tree.see(children[index])
            on_field_select()
        reload_facets()

    def selected_field_index():
        selected = field_tree.selection()
        return field_tree.index(selected[0]) if selected else None

    def on_field_select(_event=None):
        index = selected_field_index()
        if index is None:
            return
        schema = state["schema"]
        field = schema["RUN_FIELDS"][index]
        field_id.set(field)
        field_jp.set(schema.get("JP_LABEL", {}).get(field, ""))
        field_en.set(schema.get("LABEL_EN", {}).get(field, ""))
        field_type.set(type_labels.get(
            field_kind(schema, field), type_labels["text"]
        ))
        field_choices.set(",".join(schema.get("CHOICES", {}).get(field, [])))
        refresh_type_help()

    field_tree.bind("<<TreeviewSelect>>", on_field_select)

    def apply_field_edit():
        index = selected_field_index()
        if index is None or state["builtin"]:
            return
        schema = state["schema"]
        old_id = schema["RUN_FIELDS"][index]
        new_id = field_id.get().strip()
        if not new_id or not _PACK_NAME_RE.fullmatch(new_id):
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.invalid_field_id"),
                parent=top,
            )
            return
        if new_id != old_id and new_id in schema["RUN_FIELDS"]:
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.duplicate_field"),
                parent=top,
            )
            return

        schema["RUN_FIELDS"][index] = new_id
        for key in ("JP_LABEL", "LABEL_EN", "FIELD_TYPES", "CHOICES"):
            schema.setdefault(key, {})
        schema["JP_LABEL"][new_id] = field_jp.get().strip()
        schema["LABEL_EN"][new_id] = field_en.get().strip()
        kind = selected_field_kind()
        schema["FIELD_TYPES"][new_id] = kind
        if kind == "choice":
            schema["CHOICES"][new_id] = [
                value.strip() for value in field_choices.get().split(",") if value.strip()
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
        reload_field_tree(index)

    apply_field_button.configure(command=apply_field_edit)

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
        reload_field_tree(len(schema["RUN_FIELDS"]) - 1)

    def delete_field():
        index = selected_field_index()
        if index is None or state["builtin"]:
            return
        schema = state["schema"]
        field = schema["RUN_FIELDS"][index]
        if field == "run_id":
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.run_id_required"),
                parent=top,
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
        reload_field_tree(index)

    def move_field(delta):
        index = selected_field_index()
        if index is None or state["builtin"]:
            return
        fields = state["schema"]["RUN_FIELDS"]
        target = index + delta
        if target < 0 or target >= len(fields):
            return
        fields[index], fields[target] = fields[target], fields[index]
        reload_field_tree(target)

    ttk.Button(field_buttons, text=t("schema_editor.add"), command=add_field).pack(
        side="left", padx=(0, 4)
    )
    ttk.Button(field_buttons, text="▲", command=lambda: move_field(-1)).pack(side="left")
    ttk.Button(field_buttons, text="▼", command=lambda: move_field(1)).pack(
        side="left", padx=(4, 0)
    )
    ttk.Button(field_buttons, text=t("schema_editor.delete"), command=delete_field).pack(
        side="right"
    )

    adapter_form = ttk.Frame(tab_adapter)
    adapter_form.pack(fill="both", expand=True)
    adapter_vars = {
        "x_column": tk.StringVar(),
        "x_name": tk.StringVar(),
        "x_unit": tk.StringVar(),
        "skip_rows": tk.StringVar(value="0"),
        "delimiter": tk.StringVar(value=","),
    }
    sample_csv_var = tk.StringVar()
    sample_info_var = tk.StringVar()
    channel_unit_var = tk.StringVar()
    current_settings_var = tk.StringVar()
    adapter_headers = []
    channel_units = {}

    adapter_actions = ttk.Frame(adapter_form)
    adapter_actions.pack(side="bottom", fill="x", pady=(10, 0))

    sample_frame = ttk.LabelFrame(
        adapter_form, text=t("schema_editor.csv_sample"), padding=8
    )
    sample_frame.pack(fill="x", pady=(0, 8))
    choose_csv_button = ttk.Button(sample_frame, text=t("schema_editor.choose_csv"))
    choose_csv_button.pack(side="left")
    Tooltip(choose_csv_button, t("schema_editor.choose_csv_tip"))
    ttk.Label(
        sample_frame,
        textvariable=sample_csv_var,
        foreground="#555",
        anchor="w",
    ).pack(side="left", fill="x", expand=True, padx=(8, 0))
    ttk.Label(
        sample_frame, textvariable=sample_info_var, foreground="#777"
    ).pack(side="right", padx=(8, 0))

    options = ttk.Frame(adapter_form)
    options.pack(fill="x", pady=(0, 8))
    ttk.Label(options, text=t("schema_editor.str20")).pack(side="left")
    skip_rows_entry = ttk.Entry(
        options, textvariable=adapter_vars["skip_rows"], width=6
    )
    skip_rows_entry.pack(side="left", padx=(4, 14))
    ttk.Label(options, text=t("schema_editor.str21")).pack(side="left")
    delimiter_box = ttk.Combobox(
        options,
        textvariable=adapter_vars["delimiter"],
        values=[",", ";", "\\t"],
        width=8,
    )
    delimiter_box.pack(side="left", padx=(4, 14))
    reload_columns_button = ttk.Button(
        options, text=t("schema_editor.reload_columns")
    )
    reload_columns_button.pack(side="left")
    Tooltip(reload_columns_button, t("schema_editor.reload_columns_tip"))

    python_adapter_label = ttk.Label(
        adapter_form,
        text="",
        justify="left",
        foreground="#555",
    )
    python_adapter_label.pack(fill="x", pady=(0, 8))
    make_responsive_wrap(python_adapter_label, adapter_form)

    current_settings_frame = ttk.LabelFrame(
        adapter_form, text=t("schema_editor.current_settings"), padding=8
    )
    current_settings_frame.pack(fill="x", pady=(0, 8))
    current_settings_label = ttk.Label(
        current_settings_frame,
        textvariable=current_settings_var,
        justify="left",
        foreground="#333",
    )
    current_settings_label.pack(fill="x")
    make_responsive_wrap(current_settings_label, current_settings_frame, margin=20)

    mapping = ttk.Frame(adapter_form)
    mapping.pack(fill="both", expand=True)
    x_frame = ttk.LabelFrame(
        mapping, text=t("schema_editor.x_axis_settings"), padding=10
    )
    channel_frame = ttk.LabelFrame(
        mapping, text=t("schema_editor.channel_settings"), padding=10
    )

    mapping_layout = tk.StringVar(value="")

    def update_mapping_layout(event=None):
        width = event.width if event is not None else mapping.winfo_width()
        mode = adapter_mapping_layout(width)
        if mode == mapping_layout.get():
            return
        mapping_layout.set(mode)
        x_frame.grid_forget()
        channel_frame.grid_forget()
        if mode == "stacked":
            mapping.columnconfigure(0, weight=1, minsize=0)
            mapping.columnconfigure(1, weight=0, minsize=0)
            mapping.rowconfigure(0, weight=0)
            mapping.rowconfigure(1, weight=1)
            x_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
            channel_frame.grid(row=1, column=0, sticky="nsew")
        else:
            mapping.columnconfigure(0, weight=1, minsize=240)
            mapping.columnconfigure(1, weight=2, minsize=320)
            mapping.rowconfigure(0, weight=1)
            mapping.rowconfigure(1, weight=0)
            x_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
            channel_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

    mapping.bind("<Configure>", update_mapping_layout, add="+")
    mapping.after_idle(update_mapping_layout)

    ttk.Label(x_frame, text=t("schema_editor.str16")).pack(anchor="w")
    x_column_box = ttk.Combobox(
        x_frame,
        textvariable=adapter_vars["x_column"],
        state="readonly",
    )
    x_column_box.pack(fill="x", pady=(2, 10))
    ttk.Label(x_frame, text=t("schema_editor.x_name")).pack(anchor="w")
    ttk.Entry(
        x_frame, textvariable=adapter_vars["x_name"]
    ).pack(fill="x", pady=(2, 10))
    ttk.Label(x_frame, text=t("schema_editor.str17")).pack(anchor="w")
    ttk.Entry(
        x_frame, textvariable=adapter_vars["x_unit"]
    ).pack(fill="x", pady=(2, 0))

    channel_help_label = ttk.Label(
        channel_frame,
        text=t("schema_editor.channel_help"),
        justify="left",
    )
    channel_help_label.pack(fill="x", pady=(0, 6))
    make_responsive_wrap(channel_help_label, channel_frame, margin=20)
    channel_list_frame = ttk.Frame(channel_frame)
    channel_list_frame.pack(fill="both", expand=True)
    channel_tree = ttk.Treeview(
        channel_list_frame,
        columns=("column", "unit"),
        show="headings",
        selectmode="extended",
        height=8,
    )
    configure_treeview_rows(channel_tree)
    channel_tree.heading("column", text=t("schema_editor.channel_column"))
    channel_tree.heading("unit", text=t("schema_editor.channel_unit"))
    channel_tree.column("column", width=190, anchor="w")
    channel_tree.column("unit", width=90, anchor="w")
    channel_tree.pack(side="left", fill="both", expand=True)
    channel_scroll = ttk.Scrollbar(
        channel_list_frame, orient="vertical", command=channel_tree.yview
    )
    channel_scroll.pack(side="right", fill="y")
    channel_tree.configure(yscrollcommand=channel_scroll.set)

    selection_row = ttk.Frame(channel_frame)
    selection_row.pack(fill="x", pady=(5, 0))
    ttk.Button(
        selection_row,
        text=t("schema_editor.select_all"),
        command=lambda: channel_tree.selection_set(
            channel_tree.get_children()
        ),
    ).pack(side="left")
    ttk.Button(
        selection_row,
        text=t("schema_editor.clear_selection"),
        command=lambda: channel_tree.selection_remove(
            channel_tree.get_children()
        ),
    ).pack(side="left", padx=(6, 0))

    unit_row = ttk.Frame(channel_frame)
    unit_row.pack(fill="x", pady=(6, 0))
    ttk.Label(unit_row, text=t("schema_editor.channel_unit")).pack(side="left")
    ttk.Entry(
        unit_row, textvariable=channel_unit_var, width=14
    ).pack(side="left", padx=(4, 6))
    apply_unit_button = ttk.Button(
        unit_row, text=t("schema_editor.apply_unit")
    )
    apply_unit_button.pack(side="left")

    def delimiter_value():
        value = adapter_vars["delimiter"].get()
        return "\t" if value == "\\t" else value

    def delimiter_label(value):
        return "\\t" if value == "\t" else value

    def parse_skip_rows():
        try:
            value = int(adapter_vars["skip_rows"].get().strip() or "0")
            if value < 0:
                raise ValueError
            return value
        except ValueError:
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.invalid_skip"),
                parent=top,
            )
            return None

    def selected_channel_names():
        selected = set(channel_tree.selection())
        return [
            channel_tree.item(item, "values")[0]
            for item in channel_tree.get_children()
            if item in selected
        ]

    def remember_channel_units():
        for item in channel_tree.get_children():
            name, unit = channel_tree.item(item, "values")
            channel_units[name] = unit

    def reload_channel_tree(headers, selected_names=None):
        remember_channel_units()
        selected_names = set(selected_names or [])
        x_column = adapter_vars["x_column"].get()
        channel_tree.delete(*channel_tree.get_children())
        for index, name in enumerate(headers):
            if name == x_column:
                continue
            item = channel_tree.insert(
                "", "end", iid=f"channel-{index}",
                tags=(stripe_tag(index),),
                values=(name, channel_units.get(name, "")),
            )
            if name in selected_names:
                channel_tree.selection_add(item)

    def on_x_column_changed(_event=None):
        selected = selected_channel_names()
        reload_channel_tree(adapter_headers, selected)
        if not adapter_vars["x_name"].get().strip():
            adapter_vars["x_name"].set(adapter_vars["x_column"].get())

    x_column_box.bind("<<ComboboxSelected>>", on_x_column_changed)

    def apply_channel_unit():
        unit = channel_unit_var.get().strip()
        for item in channel_tree.selection():
            name, _old_unit = channel_tree.item(item, "values")
            channel_units[name] = unit
            channel_tree.item(item, values=(name, unit))

    apply_unit_button.configure(command=apply_channel_unit)

    def set_adapter_mapping_state(enabled):
        state_name = "normal" if enabled else "disabled"
        readonly_state = "readonly" if enabled else "disabled"
        x_column_box.configure(state=readonly_state)
        for widget in (x_frame, channel_frame):
            for child in widget.winfo_children():
                if child is channel_help_label:
                    continue
                try:
                    child.configure(state=state_name)
                except tk.TclError:
                    pass
                for grandchild in child.winfo_children():
                    try:
                        grandchild.configure(state=state_name)
                    except tk.TclError:
                        pass
        channel_tree.configure(selectmode="extended" if enabled else "none")

    def set_adapter_settings_state(enabled, edit_state="normal"):
        state_name = edit_state if enabled else "disabled"
        readonly_state = "readonly" if state_name == "normal" else "disabled"
        choose_csv_button.configure(state=state_name)
        skip_rows_entry.configure(state=state_name)
        delimiter_box.configure(state=readonly_state)
        reload_columns_button.configure(state=state_name)
        apply_adapter_button.configure(state=state_name)
        test_adapter_button.configure(state=state_name)
        apply_unit_button.configure(state=state_name)
        set_adapter_mapping_state(state_name == "normal")

    def load_csv_columns(path=None, auto_detect=True):
        nonlocal adapter_headers
        if not path:
            path = filedialog.askopenfilename(
                title=t("schema_editor.str22"),
                filetypes=[("CSV", "*.csv"), (t("schema_editor.all_files"), "*.*")],
                parent=top,
            )
        if not path:
            return False
        skip_rows = parse_skip_rows()
        if skip_rows is None:
            return False
        try:
            from evidex.core.nocode_adapter import inspect_csv

            inspected = inspect_csv(
                path,
                skip_rows=skip_rows,
                delimiter=None if auto_detect else delimiter_value(),
            )
        except Exception as error:
            messagebox.showerror(
                t("schema_editor.str26"), str(error), parent=top
            )
            return False

        sample_csv_var.set(str(path))
        adapter_vars["delimiter"].set(
            delimiter_label(inspected["delimiter"])
        )
        sample_info_var.set(
            t(
                "schema_editor.csv_detected",
                encoding=inspected["encoding"],
                columns=len(inspected["header"]),
            )
        )
        adapter_headers = list(inspected["header"])
        x_column_box.configure(values=adapter_headers)
        current_x = adapter_vars["x_column"].get()
        if current_x not in adapter_headers:
            current_x = adapter_headers[0]
            adapter_vars["x_column"].set(current_x)
        if not adapter_vars["x_name"].get().strip():
            adapter_vars["x_name"].set(current_x)

        configured = state.get("adapter") or {}
        selected = [
            name for name in configured.get("channel_columns", [])
            if name in adapter_headers and name != current_x
        ]
        if not selected:
            selected = [name for name in adapter_headers if name != current_x]
        reload_channel_tree(adapter_headers, selected)
        return True

    choose_csv_button.configure(command=lambda: load_csv_columns(auto_detect=True))
    reload_columns_button.configure(
        command=lambda: load_csv_columns(
            sample_csv_var.get() or None, auto_detect=False
        )
    )

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
        current_settings_var.set("\n".join(lines))

    def apply_adapter_edit():
        x_column = adapter_vars["x_column"].get().strip()
        channel_columns = selected_channel_names()
        if state["python_adapter"] and not x_column and not channel_columns:
            state["adapter"] = None
            refresh_current_settings()
            return True
        if not x_column or not channel_columns:
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.adapter_columns_required"),
                parent=top,
            )
            return False
        skip_rows = parse_skip_rows()
        if skip_rows is None:
            return False
        delimiter = delimiter_value()
        if len(delimiter) != 1:
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.invalid_delimiter"),
                parent=top,
            )
            return False
        state["adapter"] = {
            "file_format": "csv",
            "encoding_fallback": ["utf-8-sig", "cp932"],
            "skip_rows": skip_rows,
            "x_column": x_column,
            "x_name": adapter_vars["x_name"].get().strip(),
            "x_unit": adapter_vars["x_unit"].get().strip(),
            "channel_columns": channel_columns,
            "channel_units": [
                channel_units.get(name, "") for name in channel_columns
            ],
            "delimiter": delimiter,
        }
        refresh_current_settings()
        return True

    def show_signal_preview(signal, path):
        preview = tk.Toplevel(top)
        preview.title(t("schema_editor.preview_title"))
        preview.geometry("760x560")
        preview.minsize(560, 400)
        preview.transient(top)

        ttk.Label(
            preview,
            text=t(
                "schema_editor.preview_summary",
                file=Path(path).name,
                points=len(signal.x.values),
                channels=len(signal.channels),
            ),
            padding=(10, 8),
        ).pack(fill="x")

        try:
            from evidex.gui_runtime import MPL
            if MPL:
                from matplotlib.figure import Figure
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

                figure = Figure(figsize=(7, 2.6), dpi=100)
                axis = figure.add_subplot(111)
                for channel in signal.channels:
                    axis.plot(
                        signal.x.values, channel.values, label=channel.name
                    )
                x_unit = f" [{signal.x.unit}]" if signal.x.unit else ""
                axis.set_xlabel(f"{signal.x.name}{x_unit}")
                axis.set_ylabel(t("schema_editor.preview_value"))
                axis.grid(True, alpha=0.3)
                axis.legend(fontsize=8)
                figure.tight_layout()
                canvas = FigureCanvasTkAgg(figure, master=preview)
                canvas.draw()
                canvas.get_tk_widget().pack(fill="both", expand=True, padx=10)
                preview._preview_canvas = canvas
        except Exception:
            pass

        table_frame = ttk.Frame(preview, padding=(10, 6))
        table_frame.pack(fill="both", expand=True)
        columns = ["x"] + [f"channel-{i}" for i in range(len(signal.channels))]
        table = ttk.Treeview(
            table_frame, columns=columns, show="headings", height=8
        )
        configure_treeview_rows(table)
        table.heading(
            "x",
            text=f"{signal.x.name}"
                 f"{f' [{signal.x.unit}]' if signal.x.unit else ''}",
        )
        table.column("x", width=110, anchor="e")
        for index, channel in enumerate(signal.channels):
            key = f"channel-{index}"
            label = channel.name + (
                f" [{channel.unit}]" if channel.unit else ""
            )
            table.heading(key, text=label)
            table.column(key, width=120, anchor="e")
        row_count = min(100, len(signal.x.values))
        for index in range(row_count):
            table.insert(
                "", "end",
                tags=(stripe_tag(index),),
                values=[signal.x.values[index]] + [
                    channel.values[index] for channel in signal.channels
                ],
            )
        table.pack(side="left", fill="both", expand=True)
        table_scroll = ttk.Scrollbar(
            table_frame, orient="vertical", command=table.yview
        )
        table_scroll.pack(side="right", fill="y")
        table.configure(yscrollcommand=table_scroll.set)
        ttk.Button(
            preview, text=t("btn.close"), command=preview.destroy
        ).pack(anchor="e", padx=10, pady=(0, 10))
        preview._preview_table = table
        return preview

    def test_parse():
        path = sample_csv_var.get()
        if not path and not load_csv_columns(auto_detect=True):
            return
        path = sample_csv_var.get()
        if not apply_adapter_edit():
            return
        try:
            if state["adapter"] is None:
                name = current_pack.get()
                if name in registry:
                    import importlib

                    module = importlib.import_module(registry[name])
                    pack = PackInterface(name, module=module)
                else:
                    pack = PackInterface(name, user_path=str(user_pack_dir(name)))
                signal = pack.parse(path)
            else:
                from evidex.core.nocode_adapter import parse_with_config

                signal = parse_with_config(path, state["adapter"])
            show_signal_preview(signal, path)
        except Exception as error:
            messagebox.showerror(t("schema_editor.str26"), str(error), parent=top)

    apply_adapter_button = ttk.Button(
        adapter_actions, text=t("schema_editor.str27"), command=apply_adapter_edit
    )
    apply_adapter_button.pack(side="left")
    Tooltip(apply_adapter_button, t("schema_editor.apply_adapter_tip"))
    test_adapter_button = ttk.Button(
        adapter_actions, text=t("schema_editor.str28"), command=test_parse
    )
    test_adapter_button.pack(side="left", padx=(8, 0))
    Tooltip(test_adapter_button, t("schema_editor.test_adapter_tip"))

    display_intro = ttk.Label(
        tab_display,
        text=t("schema_editor.display_intro"),
        justify="left",
        foreground="#555",
    )
    display_intro.pack(fill="x", pady=(0, 8))
    make_responsive_wrap(display_intro, tab_display)

    display_tabs = ttk.Notebook(tab_display)
    display_tabs.pack(fill="both", expand=True)
    facet_frame = ttk.Frame(display_tabs, padding=10)
    color_frame = ttk.Frame(display_tabs, padding=10)
    display_tabs.add(facet_frame, text=t("schema_editor.facets"))
    display_tabs.add(color_frame, text=t("schema_editor.features"))

    facet_help = ttk.Label(
        facet_frame,
        text=t("schema_editor.facets_help"),
        justify="left",
        foreground="#555",
    )
    facet_help.pack(fill="x", pady=(0, 8))
    make_responsive_wrap(facet_help, facet_frame, margin=20)

    facet_list = tk.Listbox(facet_frame, selectmode=tk.MULTIPLE, exportselection=False)
    facet_list.pack(fill="both", expand=True)

    color_vars = {grade: tk.StringVar() for grade in "ABC"}
    feature_vars = {
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
    make_responsive_wrap(feature_intro, color_frame, margin=20)

    for row, name in enumerate(feature_vars, start=1):
        check = ttk.Checkbutton(
            color_frame,
            text=t(f"schema_editor.feature_{name}"),
            variable=feature_vars[name],
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
        make_responsive_wrap(description, color_frame, margin=44)

    ttk.Separator(color_frame).grid(
        row=9, column=0, columnspan=3, sticky="ew", pady=(8, 6)
    )
    grade_color_title = ttk.Label(
        color_frame, text=t("schema_editor.colors")
    )
    grade_color_title.grid(
        row=10, column=0, columnspan=3, sticky="w"
    )

    def choose_color(grade):
        _rgb, color = colorchooser.askcolor(color_vars[grade].get(), parent=top)
        if color:
            color_vars[grade].set(color.upper())

    grade_color_widgets = [grade_color_title]
    for row, grade in enumerate("ABC", start=11):
        ttk.Label(color_frame, text=f"{grade}:").grid(row=row, column=0, sticky="w", pady=4)
        color_entry = ttk.Entry(
            color_frame, textvariable=color_vars[grade], width=12
        )
        color_entry.grid(
            row=row, column=1, sticky="ew", padx=(6, 4), pady=4
        )
        color_button = ttk.Button(
            color_frame,
            text=t("schema_editor.choose_color"),
            command=lambda value=grade: choose_color(value),
        )
        color_button.grid(row=row, column=2, pady=4)
        grade_color_widgets.extend((color_entry, color_button))
    color_frame.columnconfigure(1, weight=1)

    def update_grade_color_state(*_):
        state_name = "normal" if feature_vars["grading"].get() else "disabled"
        for widget in grade_color_widgets[1:]:
            widget.configure(state=state_name)

    feature_vars["grading"].trace_add("write", update_grade_color_state)
    update_grade_color_state()

    def reload_facets():
        if not hasattr(facet_list, "delete"):
            return
        schema = state["schema"]
        enabled = {facet.get("field") for facet in schema.get("facets", [])}
        facet_list.delete(0, tk.END)
        for index, field in enumerate(schema.get("RUN_FIELDS", [])):
            label = (
                schema.get("JP_LABEL", {}).get(field)
                or schema.get("LABEL_EN", {}).get(field)
                or field
            )
            facet_list.insert(tk.END, f"{label}  ({field})")
            if field in enabled:
                facet_list.selection_set(index)

    def apply_display_edit():
        schema = state["schema"]
        selected = set(facet_list.curselection())
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
            for name, variable in feature_vars.items()
        }
        if features["grading"]:
            for grade in "ABC":
                value = color_vars[grade].get().strip()
                if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
                    messagebox.showerror(
                        t("schema_editor.error_title"),
                        t("schema_editor.invalid_color", grade=grade),
                        parent=top,
                    )
                    return False
                colors[grade] = value.upper()
        schema["facets"] = facets
        schema["GCOL"] = colors
        schema["features"] = features
        state["viz"] = {"facets": copy.deepcopy(facets), "GCOL": colors.copy()}
        return True

    apply_display_button = ttk.Button(
        tab_display,
        text=t("schema_editor.apply_screen_settings"),
        command=apply_display_edit,
    )
    apply_display_button.pack(side="bottom", anchor="e", pady=(8, 0))

    def load_pack(pack_name):
        builtin = pack_name in registry
        try:
            if builtin:
                schema = load_schema(pack_name)
                base = pack_resource_dir(pack_name)
            else:
                base = user_pack_dir(pack_name)
                with (base / "schema.json").open("r", encoding="utf-8") as handle:
                    schema = json.load(handle)
            adapter = {}
            adapter_path = base / "adapter_config.json"
            if adapter_path.is_file():
                with adapter_path.open("r", encoding="utf-8") as handle:
                    adapter = json.load(handle)
            viz = {}
            viz_path = base / "viz.json"
            if viz_path.is_file():
                with viz_path.open("r", encoding="utf-8") as handle:
                    viz = json.load(handle)
        except Exception as error:
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.load_failed", error=error),
                parent=top,
            )
            return

        state.update(
            schema=copy.deepcopy(schema),
            adapter=copy.deepcopy(adapter),
            viz=copy.deepcopy(viz),
            builtin=builtin,
            python_adapter=(base / "adapter.py").is_file(),
        )
        active_name = settings.get("active_pack", config.DEFAULT_PACK)
        selected_pack_label.configure(
            text=(
                t("schema_editor.active_pack_status")
                if pack_name == active_name
                else ""
            )
        )
        reload_field_tree(0)
        for key, variable in adapter_vars.items():
            value = adapter.get(key, "")
            variable.set(str(value))
        adapter_vars["skip_rows"].set(str(adapter.get("skip_rows", 0)))
        adapter_vars["delimiter"].set(
            delimiter_label(adapter.get("delimiter", ","))
        )
        sample_csv_var.set("")
        sample_info_var.set("")
        configured_columns = list(adapter.get("channel_columns", []))
        configured_units = list(adapter.get("channel_units", []))
        channel_units.clear()
        channel_units.update({
            name: configured_units[index] if index < len(configured_units) else ""
            for index, name in enumerate(configured_columns)
        })
        adapter_headers[:] = []
        if adapter.get("x_column"):
            adapter_headers.append(adapter["x_column"])
        adapter_headers.extend(
            name for name in configured_columns if name not in adapter_headers
        )
        x_column_box.configure(values=adapter_headers)
        reload_channel_tree(adapter_headers, configured_columns)
        python_adapter_label.configure(
            text=t(csv_guidance_key(pack_name, state["python_adapter"]))
        )
        refresh_current_settings()
        for grade in "ABC":
            color_vars[grade].set(schema.get("GCOL", {}).get(grade, "#808080"))
        features = schema.get("features", {})
        for name, variable in feature_vars.items():
            variable.set(bool(features.get(name, False)))
        update_grade_color_state()

        edit_state = "disabled" if builtin else "normal"
        custom_reader_only = state["python_adapter"] and not state["adapter"]
        save_button.configure(state=edit_state)
        apply_field_button.configure(state=edit_state)
        apply_display_button.configure(state=edit_state)
        set_adapter_settings_state(not custom_reader_only, edit_state)
        readonly_label.configure(text=t("schema_editor.str6") if builtin else "")

    def refresh_pack_list(select_name=None):
        names = get_pack_names()
        pack_list.delete(0, tk.END)
        for name in names:
            pack_list.insert(tk.END, name)
        pack_selector.configure(values=names)
        target = choose_initial_pack(
            names,
            select_name or current_pack.get(),
            settings.get("active_pack", config.DEFAULT_PACK),
        )
        index = names.index(target) if target is not None else None
        if index is not None:
            pack_list.selection_set(index)
            pack_list.activate(index)
            pack_list.see(index)
            current_pack.set(names[index])
            load_pack(names[index])

    def on_pack_select(_event=None):
        selected = pack_list.curselection()
        if not selected:
            return
        name = pack_list.get(selected[0])
        current_pack.set(name)
        load_pack(name)

    def on_pack_selector_select(_event=None):
        name = current_pack.get()
        names = list(pack_selector.cget("values"))
        if name not in names:
            return
        index = names.index(name)
        pack_list.selection_clear(0, tk.END)
        pack_list.selection_set(index)
        pack_list.activate(index)
        pack_list.see(index)
        load_pack(name)

    pack_list.bind("<<ListboxSelect>>", on_pack_select)
    pack_selector.bind("<<ComboboxSelected>>", on_pack_selector_select)

    def save_current_pack():
        try:
            if not apply_adapter_edit() or not apply_display_edit():
                return
            name = current_pack.get()
            save_user_pack(name, state["schema"], state["adapter"], state["viz"])
            use_pack = messagebox.askyesno(
                t("schema_editor.success_title"),
                t("schema_editor.saved_use_pack", pack_name=name),
                parent=top,
            )
            if use_pack:
                from evidex.core import settings

                settings.set("active_pack", name)
                messagebox.showinfo(
                    t("schema_editor.success_title"),
                    t("schema_editor.restart_to_apply"),
                    parent=top,
                )
            refresh_pack_list(name)
            notebook.select(tab_adapter_page)
        except Exception as error:
            messagebox.showerror(t("schema_editor.error_title"), str(error), parent=top)

    save_button.configure(command=save_current_pack)

    def create_pack():
        name = simpledialog.askstring(
            t("schema_editor.str37"), t("schema_editor.str38"), parent=top
        )
        if not name:
            return
        try:
            name = validate_pack_name(name)
            schema = _blank_schema()
            save_user_pack(
                name,
                schema,
                _blank_adapter(),
                {"facets": [], "GCOL": schema["GCOL"].copy()},
            )
            refresh_pack_list(name)
            notebook.select(tab_adapter_page)
            top.after_idle(choose_csv_button.focus_set)
        except Exception as error:
            messagebox.showerror(t("schema_editor.error_title"), str(error), parent=top)

    def duplicate_selected():
        selected = pack_list.curselection()
        if not selected:
            return
        source_name = pack_list.get(selected[0])
        name = simpledialog.askstring(
            t("schema_editor.str33"), t("schema_editor.str34"), parent=top
        )
        if not name:
            return
        try:
            destination = duplicate_pack(source_name, name)
            refresh_pack_list(destination.name)
            notebook.select(tab_adapter_page)
        except Exception as error:
            messagebox.showerror(t("schema_editor.error_title"), str(error), parent=top)

    def delete_selected_pack():
        selected = pack_list.curselection()
        if not selected:
            return
        name = pack_list.get(selected[0])
        if name in registry:
            messagebox.showerror(
                t("schema_editor.error_title"), t("schema_editor.str30"), parent=top
            )
            return
        if not messagebox.askyesno(
            t("schema_editor.delete_title"),
            t("schema_editor.delete_confirm", pack_name=name),
            parent=top,
        ):
            return
        try:
            delete_user_pack(name)
            refresh_pack_list()
        except Exception as error:
            messagebox.showerror(t("schema_editor.error_title"), str(error), parent=top)

    new_pack_button = ttk.Button(
        left_buttons, text=t("schema_editor.str44"), command=create_pack
    )
    duplicate_button = ttk.Button(
        left_buttons, text=t("schema_editor.str36"), command=duplicate_selected
    )
    delete_pack_button = ttk.Button(
        left_buttons, text=t("schema_editor.delete"), command=delete_selected_pack
    )
    new_pack_button.grid(
        row=0, column=0, columnspan=2, sticky="ew", pady=(0, 3)
    )
    duplicate_button.grid(row=1, column=0, sticky="ew", padx=(0, 2))
    delete_pack_button.grid(row=1, column=1, sticky="ew", padx=(2, 0))
    Tooltip(new_pack_button, t("schema_editor.new_pack_tip"))
    Tooltip(duplicate_button, t("schema_editor.duplicate_tip"))
    Tooltip(delete_pack_button, t("schema_editor.delete_tip"))
    Tooltip(save_button, t("schema_editor.save_tip"))

    def initialize_sashes():
        """Give editors useful initial widths without overriding later user moves."""
        top.update_idletasks()
        main_width = main_pw.winfo_width()
        if main_width > 500:
            main_pw.sashpos(0, max(190, min(220, main_width // 3)))
        field_width = field_pw.winfo_width()
        if field_width > 420:
            field_pw.sashpos(
                0, max(200, min(field_width - 220, int(field_width * 0.65)))
            )

    top.after_idle(initialize_sashes)

    top._schema_editor_save = save_current_pack
    top._schema_editor_state = state
    top._schema_editor_main_pane = main_pw
    top._schema_editor_field_pane = field_pw
    top._schema_editor_field_tree = field_tree
    top._schema_editor_field_hscroll = field_hscroll
    top._schema_editor_pack_buttons = (
        new_pack_button,
        duplicate_button,
        delete_pack_button,
    )
    top._schema_editor_save_button = save_button
    top._schema_editor_current_pack = current_pack
    top._schema_editor_pack_selector = pack_selector
    top._schema_editor_selected_pack_label = selected_pack_label
    top._schema_editor_notebook = notebook
    top._schema_editor_adapter_tab = tab_adapter_page
    top._schema_editor_field_intro = field_intro
    top._schema_editor_field_type_box = field_type_box
    top._schema_editor_field_type_help = field_type_help_label
    top._schema_editor_apply_field_button = apply_field_button
    top._schema_editor_display_tabs = display_tabs
    top._schema_editor_python_adapter_note = python_adapter_label
    top._schema_editor_current_settings = current_settings_label
    top._schema_editor_current_settings_var = current_settings_var
    top._schema_editor_choose_csv_button = choose_csv_button
    top._schema_editor_skip_rows_entry = skip_rows_entry
    top._schema_editor_delimiter_box = delimiter_box
    top._schema_editor_reload_columns_button = reload_columns_button
    top._schema_editor_apply_adapter_button = apply_adapter_button
    top._schema_editor_x_column_box = x_column_box
    top._schema_editor_channel_tree = channel_tree
    top._schema_editor_adapter_mapping = mapping
    top._schema_editor_adapter_mapping_layout = mapping_layout
    top._schema_editor_x_axis_frame = x_frame
    top._schema_editor_channel_frame = channel_frame
    top._schema_editor_test_adapter = test_parse
    top._schema_editor_test_adapter_button = test_adapter_button
    top._schema_editor_page_canvases = (
        fields_canvas,
        adapter_canvas,
        display_canvas,
    )
    top._schema_editor_page_scrollbars = (
        fields_scrollbar,
        adapter_scrollbar,
        display_scrollbar,
    )
    enable_page_mousewheel(tab_fields, fields_canvas)
    enable_page_mousewheel(tab_adapter, adapter_canvas)
    enable_page_mousewheel(tab_display, display_canvas)
    refresh_pack_list()
    return top
