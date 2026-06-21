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


class SchemaEditorWindow(tk.Toplevel):
    """パック管理ウィンドウ。"""

    def __init__(self, parent):
        super().__init__(parent)
        from evidex.core import settings

        self._settings = settings
        self._schema = {}
        self._adapter = {}
        self._viz = {}
        self._builtin = True
        self._python_adapter = False
        self._adapter_headers = []
        self._channel_units = {}

        self.title(t("schema_editor.str1"))
        screen_w = max(640, self.winfo_screenwidth())
        screen_h = max(480, self.winfo_screenheight())
        width = min(screen_w, min(1100, max(680, screen_w - 40)))
        height = min(screen_h, min(720, max(500, screen_h - 80)))
        self.geometry(f"{width}x{height}")
        self.minsize(min(680, screen_w), min(500, screen_h))
        self.transient(parent)
        self.grab_set()

        self._current_pack = tk.StringVar(
            value=self._settings.get("active_pack", config.DEFAULT_PACK)
        )

        self._build_left_panel()
        self._build_right_panel()
        self._build_fields_tab()
        self._build_adapter_tab()
        self._build_display_tab()
        self._build_pack_buttons()
        self._connect_signals()
        self._expose_test_attributes()

        self._enable_page_mousewheel(
            self._tab_fields, self._fields_canvas
        )
        self._enable_page_mousewheel(
            self._tab_adapter, self._adapter_canvas
        )
        self._enable_page_mousewheel(
            self._tab_display, self._display_canvas
        )
        self._refresh_pack_list()

    @property
    def _schema_editor_state(self):
        return {
            "schema": self._schema,
            "adapter": self._adapter,
            "viz": self._viz,
            "builtin": self._builtin,
            "python_adapter": self._python_adapter,
        }

    def _make_responsive_wrap(
        self, label, container, margin=24, minimum=160
    ):
        container.bind(
            "<Configure>",
            lambda event: label.configure(
                wraplength=max(minimum, event.width - margin)
            ),
            add="+",
        )

    def _add_scrollable_tab(self, notebook_widget, label):
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
        canvas.bind(
            "<Configure>",
            lambda _event: self._sync_scrollable_tab(
                canvas, content, content_window
            ),
            add="+",
        )
        content.bind(
            "<Configure>",
            lambda _event: canvas.after_idle(
                self._sync_scrollable_tab,
                canvas,
                content,
                content_window,
            ),
            add="+",
        )
        notebook_widget.add(page, text=label)
        return page, content, canvas, scrollbar

    def _sync_scrollable_tab(self, canvas, content, content_window):
        width = max(1, canvas.winfo_width())
        height = max(canvas.winfo_height(), content.winfo_reqheight())
        canvas.itemconfigure(content_window, width=width, height=height)
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _enable_page_mousewheel(self, container, canvas):
        self._bind_page_mousewheel(container, canvas)

    def _bind_page_mousewheel(self, widget, canvas):
        if widget.winfo_class() not in {
            "Listbox",
            "Treeview",
            "Text",
            "TCombobox",
        }:
            widget.bind(
                "<MouseWheel>",
                lambda event: self._scroll_page(canvas, event),
                add="+",
            )
        for child in widget.winfo_children():
            self._bind_page_mousewheel(child, canvas)

    def _scroll_page(self, canvas, event):
        first, last = canvas.yview()
        if first == 0.0 and last == 1.0:
            return None
        steps = int(-event.delta / 120)
        canvas.yview_scroll(
            steps or (-1 if event.delta > 0 else 1), "units"
        )
        return "break"

    def _build_left_panel(self):
        """左パネル: パック一覧。"""
        self._main_pw = ttk.PanedWindow(self, orient="horizontal")
        self._main_pw.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(self._main_pw)
        self._main_pw.add(left, weight=1)
        ttk.Label(left, text=t("schema_editor.str2")).pack(anchor="w", pady=(0, 4))

        # Reserve the action bar at the bottom first so it remains visible on short screens.
        self._left_buttons = ttk.Frame(left)
        self._left_buttons.pack(side="bottom", fill="x", pady=(4, 0))
        for column in range(2):
            self._left_buttons.columnconfigure(column, weight=1)

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        self._pack_list = tk.Listbox(list_frame, exportselection=False)
        self._pack_list.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self._pack_list.yview)
        scrollbar.pack(side="right", fill="y")
        self._pack_list.configure(yscrollcommand=scrollbar.set)

    def _build_right_panel(self):
        """右パネル: パック選択とタブ枠。"""
        right = ttk.Frame(self._main_pw)
        self._main_pw.add(right, weight=3)

        pack_selector_frame = ttk.Frame(right)
        pack_selector_frame.pack(fill="x", pady=(0, 4))
        ttk.Label(
            pack_selector_frame,
            text=t("schema_editor.pack_to_edit"),
        ).pack(side="left")
        self._pack_selector = ttk.Combobox(
            pack_selector_frame,
            textvariable=self._current_pack,
            state="readonly",
            width=24,
        )
        self._pack_selector.pack(side="left", padx=(6, 8))
        self._selected_pack_label = ttk.Label(pack_selector_frame, anchor="w")
        self._selected_pack_label.pack(side="left", fill="x", expand=True)

        # Reserve the save bar before the self._notebook so wide tab contents cannot hide it.
        bottom = ttk.Frame(right)
        bottom.pack(side="bottom", fill="x", pady=(8, 0))
        self._save_button = ttk.Button(bottom, text=t("schema_editor.str7"), state="disabled")
        self._save_button.pack(side="right", padx=(8, 0))
        self._readonly_label = ttk.Label(
            bottom, text=t("schema_editor.str6"), anchor="w", justify="left"
        )
        self._readonly_label.pack(side="left", fill="x", expand=True)
        self._make_responsive_wrap(
            self._readonly_label, bottom, margin=140
        )

        self._notebook = ttk.Notebook(right)
        self._notebook.pack(fill="both", expand=True)
        (
            self._tab_fields_page,
            self._tab_fields,
            self._fields_canvas,
            self._fields_scrollbar,
        ) = self._add_scrollable_tab(
            self._notebook, t("schema_editor.str3")
        )
        (
            self._tab_adapter_page,
            self._tab_adapter,
            self._adapter_canvas,
            self._adapter_scrollbar,
        ) = self._add_scrollable_tab(
            self._notebook, t("schema_editor.str4")
        )
        (
            self._tab_display_page,
            self._tab_display,
            self._display_canvas,
            self._display_scrollbar,
        ) = self._add_scrollable_tab(
            self._notebook, t("schema_editor.str5")
        )

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

    def _build_adapter_tab(self):
        """タブ2: アダプター設定。"""
        adapter_form = ttk.Frame(self._tab_adapter)
        adapter_form.pack(fill="both", expand=True)
        self._adapter_vars = {
            "x_column": tk.StringVar(),
            "x_name": tk.StringVar(),
            "x_unit": tk.StringVar(),
            "skip_rows": tk.StringVar(value="0"),
            "delimiter": tk.StringVar(value=","),
        }
        self._sample_csv_var = tk.StringVar()
        self._sample_info_var = tk.StringVar()
        self._channel_unit_var = tk.StringVar()
        self._current_settings_var = tk.StringVar()
        self._adapter_headers = []
        self._channel_units = {}

        adapter_actions = ttk.Frame(adapter_form)
        adapter_actions.pack(side="bottom", fill="x", pady=(10, 0))

        sample_frame = ttk.LabelFrame(
            adapter_form, text=t("schema_editor.csv_sample"), padding=8
        )
        sample_frame.pack(fill="x", pady=(0, 8))
        self._choose_csv_button = ttk.Button(sample_frame, text=t("schema_editor.choose_csv"))
        self._choose_csv_button.pack(side="left")
        Tooltip(self._choose_csv_button, t("schema_editor.choose_csv_tip"))
        ttk.Label(
            sample_frame,
            textvariable=self._sample_csv_var,
            foreground="#555",
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=(8, 0))
        ttk.Label(
            sample_frame, textvariable=self._sample_info_var, foreground="#777"
        ).pack(side="right", padx=(8, 0))

        options = ttk.Frame(adapter_form)
        options.pack(fill="x", pady=(0, 8))
        ttk.Label(options, text=t("schema_editor.str20")).pack(side="left")
        self._skip_rows_entry = ttk.Entry(
            options, textvariable=self._adapter_vars["skip_rows"], width=6
        )
        self._skip_rows_entry.pack(side="left", padx=(4, 14))
        ttk.Label(options, text=t("schema_editor.str21")).pack(side="left")
        self._delimiter_box = ttk.Combobox(
            options,
            textvariable=self._adapter_vars["delimiter"],
            values=[",", ";", "\\t"],
            width=8,
        )
        self._delimiter_box.pack(side="left", padx=(4, 14))
        self._reload_columns_button = ttk.Button(
            options, text=t("schema_editor.reload_columns")
        )
        self._reload_columns_button.pack(side="left")
        Tooltip(self._reload_columns_button, t("schema_editor.reload_columns_tip"))

        self._python_adapter_label = ttk.Label(
            adapter_form,
            text="",
            justify="left",
            foreground="#555",
        )
        self._python_adapter_label.pack(fill="x", pady=(0, 8))
        self._make_responsive_wrap(
            self._python_adapter_label, adapter_form
        )

        current_settings_frame = ttk.LabelFrame(
            adapter_form, text=t("schema_editor.current_settings"), padding=8
        )
        current_settings_frame.pack(fill="x", pady=(0, 8))
        self._current_settings_label = ttk.Label(
            current_settings_frame,
            textvariable=self._current_settings_var,
            justify="left",
            foreground="#333",
        )
        self._current_settings_label.pack(fill="x")
        self._make_responsive_wrap(
            self._current_settings_label,
            current_settings_frame,
            margin=20,
        )

        self._mapping = ttk.Frame(adapter_form)
        self._mapping.pack(fill="both", expand=True)
        self._x_frame = ttk.LabelFrame(
            self._mapping, text=t("schema_editor.x_axis_settings"), padding=10
        )
        self._channel_frame = ttk.LabelFrame(
            self._mapping, text=t("schema_editor.channel_settings"), padding=10
        )

        self._mapping_layout = tk.StringVar(value="")
        ttk.Label(self._x_frame, text=t("schema_editor.str16")).pack(anchor="w")
        self._x_column_box = ttk.Combobox(
            self._x_frame,
            textvariable=self._adapter_vars["x_column"],
            state="readonly",
        )
        self._x_column_box.pack(fill="x", pady=(2, 10))
        ttk.Label(self._x_frame, text=t("schema_editor.x_name")).pack(anchor="w")
        ttk.Entry(
            self._x_frame, textvariable=self._adapter_vars["x_name"]
        ).pack(fill="x", pady=(2, 10))
        ttk.Label(self._x_frame, text=t("schema_editor.str17")).pack(anchor="w")
        ttk.Entry(
            self._x_frame, textvariable=self._adapter_vars["x_unit"]
        ).pack(fill="x", pady=(2, 0))

        self._channel_help_label = ttk.Label(
            self._channel_frame,
            text=t("schema_editor.channel_help"),
            justify="left",
        )
        self._channel_help_label.pack(fill="x", pady=(0, 6))
        self._make_responsive_wrap(
            self._channel_help_label, self._channel_frame, margin=20
        )
        channel_list_frame = ttk.Frame(self._channel_frame)
        channel_list_frame.pack(fill="both", expand=True)
        self._channel_tree = ttk.Treeview(
            channel_list_frame,
            columns=("column", "unit"),
            show="headings",
            selectmode="extended",
            height=8,
        )
        configure_treeview_rows(self._channel_tree)
        self._channel_tree.heading("column", text=t("schema_editor.channel_column"))
        self._channel_tree.heading("unit", text=t("schema_editor.channel_unit"))
        self._channel_tree.column("column", width=190, anchor="w")
        self._channel_tree.column("unit", width=90, anchor="w")
        self._channel_tree.pack(side="left", fill="both", expand=True)
        channel_scroll = ttk.Scrollbar(
            channel_list_frame, orient="vertical", command=self._channel_tree.yview
        )
        channel_scroll.pack(side="right", fill="y")
        self._channel_tree.configure(yscrollcommand=channel_scroll.set)

        selection_row = ttk.Frame(self._channel_frame)
        selection_row.pack(fill="x", pady=(5, 0))
        unit_row = ttk.Frame(self._channel_frame)
        unit_row.pack(fill="x", pady=(6, 0))
        ttk.Label(unit_row, text=t("schema_editor.channel_unit")).pack(side="left")
        ttk.Entry(
            unit_row, textvariable=self._channel_unit_var, width=14
        ).pack(side="left", padx=(4, 6))
        self._apply_unit_button = ttk.Button(
            unit_row, text=t("schema_editor.apply_unit")
        )
        self._apply_unit_button.pack(side="left")
        self._select_all_channels_button = ttk.Button(
            selection_row, text=t("schema_editor.select_all")
        )
        self._clear_channels_button = ttk.Button(
            selection_row, text=t("schema_editor.clear_selection")
        )
        self._select_all_channels_button.pack(side="left")
        self._clear_channels_button.pack(side="left", padx=(6, 0))

        self._apply_adapter_button = ttk.Button(
            adapter_actions, text=t("schema_editor.str27")
        )
        self._apply_adapter_button.pack(side="left")
        Tooltip(
            self._apply_adapter_button,
            t("schema_editor.apply_adapter_tip"),
        )
        self._test_adapter_button = ttk.Button(
            adapter_actions, text=t("schema_editor.str28")
        )
        self._test_adapter_button.pack(side="left", padx=(8, 0))
        Tooltip(
            self._test_adapter_button,
            t("schema_editor.test_adapter_tip"),
        )

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

    def _build_pack_buttons(self):
        """左パネル下部のパック操作ボタン。"""
        self._new_pack_button = ttk.Button(
            self._left_buttons, text=t("schema_editor.str44")
        )
        self._duplicate_button = ttk.Button(
            self._left_buttons, text=t("schema_editor.str36")
        )
        self._delete_pack_button = ttk.Button(
            self._left_buttons, text=t("schema_editor.delete")
        )
        self._new_pack_button.grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 3)
        )
        self._duplicate_button.grid(
            row=1, column=0, sticky="ew", padx=(0, 2)
        )
        self._delete_pack_button.grid(
            row=1, column=1, sticky="ew", padx=(2, 0)
        )
        Tooltip(
            self._new_pack_button, t("schema_editor.new_pack_tip")
        )
        Tooltip(
            self._duplicate_button, t("schema_editor.duplicate_tip")
        )
        Tooltip(
            self._delete_pack_button, t("schema_editor.delete_tip")
        )
        Tooltip(self._save_button, t("schema_editor.save_tip"))

    def _connect_signals(self):
        """シグナルとイベントを接続する。"""
        self._field_type_box.bind(
            "<<ComboboxSelected>>", self._refresh_type_help
        )
        self._field_tree.bind(
            "<<TreeviewSelect>>", self._on_field_select
        )
        self._apply_field_button.configure(
            command=self._apply_field_edit
        )
        self._add_field_button.configure(command=self._add_field)
        self._move_field_up_button.configure(
            command=lambda: self._move_field(-1)
        )
        self._move_field_down_button.configure(
            command=lambda: self._move_field(1)
        )
        self._delete_field_button.configure(command=self._delete_field)
        self._mapping.bind(
            "<Configure>", self._update_mapping_layout, add="+"
        )
        self._mapping.after_idle(self._update_mapping_layout)
        self._x_column_box.bind(
            "<<ComboboxSelected>>", self._on_x_column_changed
        )
        self._apply_unit_button.configure(
            command=self._apply_channel_unit
        )
        self._select_all_channels_button.configure(
            command=lambda: self._channel_tree.selection_set(
                self._channel_tree.get_children()
            )
        )
        self._clear_channels_button.configure(
            command=lambda: self._channel_tree.selection_remove(
                self._channel_tree.get_children()
            )
        )
        self._choose_csv_button.configure(
            command=lambda: self._load_csv_columns(auto_detect=True)
        )
        self._reload_columns_button.configure(
            command=lambda: self._load_csv_columns(
                self._sample_csv_var.get() or None,
                auto_detect=False,
            )
        )
        self._apply_adapter_button.configure(
            command=self._apply_adapter_edit
        )
        self._test_adapter_button.configure(command=self._test_parse)
        self._feature_vars["grading"].trace_add(
            "write", self._update_grade_color_state
        )
        for grade, button in self._grade_color_buttons.items():
            button.configure(
                command=lambda value=grade: self._choose_color(value)
            )
        self._apply_display_button.configure(
            command=self._apply_display_edit
        )
        self._pack_list.bind(
            "<<ListboxSelect>>", self._on_pack_select
        )
        self._pack_selector.bind(
            "<<ComboboxSelected>>", self._on_pack_selector_select
        )
        self._save_button.configure(command=self._save_current_pack)
        self._new_pack_button.configure(command=self._create_pack)
        self._duplicate_button.configure(
            command=self._duplicate_selected
        )
        self._delete_pack_button.configure(
            command=self._delete_selected_pack
        )
        self.after_idle(self._initialize_sashes)
        self._refresh_type_help()
        self._update_grade_color_state()

    def _expose_test_attributes(self):
        """既存テスト向けの属性を公開する。"""
        self._schema_editor_save = self._save_current_pack
        self._schema_editor_main_pane = self._main_pw
        self._schema_editor_field_pane = self._field_pw
        self._schema_editor_field_tree = self._field_tree
        self._schema_editor_field_hscroll = self._field_hscroll
        self._schema_editor_pack_buttons = (
            self._new_pack_button,
            self._duplicate_button,
            self._delete_pack_button,
        )
        self._schema_editor_save_button = self._save_button
        self._schema_editor_current_pack = self._current_pack
        self._schema_editor_pack_selector = self._pack_selector
        self._schema_editor_selected_pack_label = (
            self._selected_pack_label
        )
        self._schema_editor_notebook = self._notebook
        self._schema_editor_adapter_tab = self._tab_adapter_page
        self._schema_editor_field_intro = self._field_intro
        self._schema_editor_field_type_box = self._field_type_box
        self._schema_editor_field_type_help = (
            self._field_type_help_label
        )
        self._schema_editor_apply_field_button = (
            self._apply_field_button
        )
        self._schema_editor_display_tabs = self._display_tabs
        self._schema_editor_python_adapter_note = (
            self._python_adapter_label
        )
        self._schema_editor_current_settings = (
            self._current_settings_label
        )
        self._schema_editor_current_settings_var = (
            self._current_settings_var
        )
        self._schema_editor_choose_csv_button = self._choose_csv_button
        self._schema_editor_skip_rows_entry = self._skip_rows_entry
        self._schema_editor_delimiter_box = self._delimiter_box
        self._schema_editor_reload_columns_button = (
            self._reload_columns_button
        )
        self._schema_editor_apply_adapter_button = (
            self._apply_adapter_button
        )
        self._schema_editor_x_column_box = self._x_column_box
        self._schema_editor_channel_tree = self._channel_tree
        self._schema_editor_adapter_mapping = self._mapping
        self._schema_editor_adapter_mapping_layout = self._mapping_layout
        self._schema_editor_x_axis_frame = self._x_frame
        self._schema_editor_channel_frame = self._channel_frame
        self._schema_editor_test_adapter = self._test_parse
        self._schema_editor_test_adapter_button = (
            self._test_adapter_button
        )
        self._schema_editor_page_canvases = (
            self._fields_canvas,
            self._adapter_canvas,
            self._display_canvas,
        )
        self._schema_editor_page_scrollbars = (
            self._fields_scrollbar,
            self._adapter_scrollbar,
            self._display_scrollbar,
        )

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

    def _update_mapping_layout(self, event=None):
        width = event.width if event is not None else self._mapping.winfo_width()
        mode = adapter_mapping_layout(width)
        if mode == self._mapping_layout.get():
            return
        self._mapping_layout.set(mode)
        self._x_frame.grid_forget()
        self._channel_frame.grid_forget()
        if mode == "stacked":
            self._mapping.columnconfigure(0, weight=1, minsize=0)
            self._mapping.columnconfigure(1, weight=0, minsize=0)
            self._mapping.rowconfigure(0, weight=0)
            self._mapping.rowconfigure(1, weight=1)
            self._x_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
            self._channel_frame.grid(row=1, column=0, sticky="nsew")
        else:
            self._mapping.columnconfigure(0, weight=1, minsize=240)
            self._mapping.columnconfigure(1, weight=2, minsize=320)
            self._mapping.rowconfigure(0, weight=1)
            self._mapping.rowconfigure(1, weight=0)
            self._x_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
            self._channel_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

    def _delimiter_value(self):
        value = self._adapter_vars["delimiter"].get()
        return "\t" if value == "\\t" else value

    def _delimiter_label(self, value):
        return "\\t" if value == "\t" else value

    def _parse_skip_rows(self):
        try:
            value = int(self._adapter_vars["skip_rows"].get().strip() or "0")
            if value < 0:
                raise ValueError
            return value
        except ValueError:
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.invalid_skip"),
                parent=self,
            )
            return None

    def _selected_channel_names(self):
        selected = set(self._channel_tree.selection())
        return [
            self._channel_tree.item(item, "values")[0]
            for item in self._channel_tree.get_children()
            if item in selected
        ]

    def _remember_channel_units(self):
        for item in self._channel_tree.get_children():
            name, unit = self._channel_tree.item(item, "values")
            self._channel_units[name] = unit

    def _reload_channel_tree(self, headers, selected_names=None):
        self._remember_channel_units()
        selected_names = set(selected_names or [])
        x_column = self._adapter_vars["x_column"].get()
        self._channel_tree.delete(*self._channel_tree.get_children())
        for index, name in enumerate(headers):
            if name == x_column:
                continue
            item = self._channel_tree.insert(
                "", "end", iid=f"channel-{index}",
                tags=(stripe_tag(index),),
                values=(name, self._channel_units.get(name, "")),
            )
            if name in selected_names:
                self._channel_tree.selection_add(item)

    def _on_x_column_changed(self, _event=None):
        selected = self._selected_channel_names()
        self._reload_channel_tree(self._adapter_headers, selected)
        if not self._adapter_vars["x_name"].get().strip():
            self._adapter_vars["x_name"].set(self._adapter_vars["x_column"].get())

    def _apply_channel_unit(self):
        unit = self._channel_unit_var.get().strip()
        for item in self._channel_tree.selection():
            name, _old_unit = self._channel_tree.item(item, "values")
            self._channel_units[name] = unit
            self._channel_tree.item(item, values=(name, unit))

    def _set_adapter_mapping_state(self, enabled):
        state_name = "normal" if enabled else "disabled"
        readonly_state = "readonly" if enabled else "disabled"
        self._x_column_box.configure(state=readonly_state)
        for widget in (self._x_frame, self._channel_frame):
            for child in widget.winfo_children():
                if child is self._channel_help_label:
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
        self._channel_tree.configure(selectmode="extended" if enabled else "none")

    def _set_adapter_settings_state(self, enabled, edit_state="normal"):
        state_name = edit_state if enabled else "disabled"
        readonly_state = "readonly" if state_name == "normal" else "disabled"
        self._choose_csv_button.configure(state=state_name)
        self._skip_rows_entry.configure(state=state_name)
        self._delimiter_box.configure(state=readonly_state)
        self._reload_columns_button.configure(state=state_name)
        self._apply_adapter_button.configure(state=state_name)
        self._test_adapter_button.configure(state=state_name)
        self._apply_unit_button.configure(state=state_name)
        self._set_adapter_mapping_state(state_name == "normal")

    def _load_csv_columns(self, path=None, auto_detect=True):
        if not path:
            path = filedialog.askopenfilename(
                title=t("schema_editor.str22"),
                filetypes=[("CSV", "*.csv"), (t("schema_editor.all_files"), "*.*")],
                parent=self,
            )
        if not path:
            return False
        skip_rows = self._parse_skip_rows()
        if skip_rows is None:
            return False
        try:
            from evidex.core.nocode_adapter import inspect_csv

            inspected = inspect_csv(
                path,
                skip_rows=skip_rows,
                delimiter=None if auto_detect else self._delimiter_value(),
            )
        except Exception as error:
            messagebox.showerror(
                t("schema_editor.str26"), str(error), parent=self
            )
            return False

        self._sample_csv_var.set(str(path))
        self._adapter_vars["delimiter"].set(
            self._delimiter_label(inspected["delimiter"])
        )
        self._sample_info_var.set(
            t(
                "schema_editor.csv_detected",
                encoding=inspected["encoding"],
                columns=len(inspected["header"]),
            )
        )
        self._adapter_headers = list(inspected["header"])
        self._x_column_box.configure(values=self._adapter_headers)
        current_x = self._adapter_vars["x_column"].get()
        if current_x not in self._adapter_headers:
            current_x = self._adapter_headers[0]
            self._adapter_vars["x_column"].set(current_x)
        if not self._adapter_vars["x_name"].get().strip():
            self._adapter_vars["x_name"].set(current_x)

        configured = self._adapter or {}
        selected = [
            name for name in configured.get("channel_columns", [])
            if name in self._adapter_headers and name != current_x
        ]
        if not selected:
            selected = [name for name in self._adapter_headers if name != current_x]
        self._reload_channel_tree(self._adapter_headers, selected)
        return True

    def _refresh_current_settings(self):
        lines = []
        for item in adapter_summary_lines(
            self._adapter or {},
            self._python_adapter,
        ):
            if isinstance(item, tuple):
                key, values = item
                lines.append(t(key, **values))
            else:
                lines.append(t(item))
        self._current_settings_var.set("\n".join(lines))

    def _apply_adapter_edit(self):
        x_column = self._adapter_vars["x_column"].get().strip()
        channel_columns = self._selected_channel_names()
        if self._python_adapter and not x_column and not channel_columns:
            self._adapter = None
            self._refresh_current_settings()
            return True
        if not x_column or not channel_columns:
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.adapter_columns_required"),
                parent=self,
            )
            return False
        skip_rows = self._parse_skip_rows()
        if skip_rows is None:
            return False
        delimiter = self._delimiter_value()
        if len(delimiter) != 1:
            messagebox.showerror(
                t("schema_editor.error_title"),
                t("schema_editor.invalid_delimiter"),
                parent=self,
            )
            return False
        self._adapter = {
            "file_format": "csv",
            "encoding_fallback": ["utf-8-sig", "cp932"],
            "skip_rows": skip_rows,
            "x_column": x_column,
            "x_name": self._adapter_vars["x_name"].get().strip(),
            "x_unit": self._adapter_vars["x_unit"].get().strip(),
            "channel_columns": channel_columns,
            "channel_units": [
                self._channel_units.get(name, "") for name in channel_columns
            ],
            "delimiter": delimiter,
        }
        self._refresh_current_settings()
        return True

    def _show_signal_preview(self, signal, path):
        preview = tk.Toplevel(self)
        preview.title(t("schema_editor.preview_title"))
        preview.geometry("760x560")
        preview.minsize(560, 400)
        preview.transient(self)

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

    def _test_parse(self):
        path = self._sample_csv_var.get()
        if not path and not self._load_csv_columns(auto_detect=True):
            return
        path = self._sample_csv_var.get()
        if not self._apply_adapter_edit():
            return
        try:
            if self._adapter is None:
                name = self._current_pack.get()
                if name in registry:
                    import importlib

                    module = importlib.import_module(registry[name])
                    pack = PackInterface(name, module=module)
                else:
                    pack = PackInterface(name, user_path=str(user_pack_dir(name)))
                signal = pack.parse(path)
            else:
                from evidex.core.nocode_adapter import parse_with_config

                signal = parse_with_config(path, self._adapter)
            self._show_signal_preview(signal, path)
        except Exception as error:
            messagebox.showerror(t("schema_editor.str26"), str(error), parent=self)

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

    def _load_pack(self, pack_name):
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
                parent=self,
            )
            return

        self._schema = copy.deepcopy(schema)
        self._adapter = copy.deepcopy(adapter)
        self._viz = copy.deepcopy(viz)
        self._builtin = builtin
        self._python_adapter = (base / "adapter.py").is_file()
        active_name = self._settings.get("active_pack", config.DEFAULT_PACK)
        self._selected_pack_label.configure(
            text=(
                t("schema_editor.active_pack_status")
                if pack_name == active_name
                else ""
            )
        )
        self._reload_field_tree(0)
        for key, variable in self._adapter_vars.items():
            value = adapter.get(key, "")
            variable.set(str(value))
        self._adapter_vars["skip_rows"].set(str(adapter.get("skip_rows", 0)))
        self._adapter_vars["delimiter"].set(
            self._delimiter_label(adapter.get("delimiter", ","))
        )
        self._sample_csv_var.set("")
        self._sample_info_var.set("")
        configured_columns = list(adapter.get("channel_columns", []))
        configured_units = list(adapter.get("channel_units", []))
        self._channel_units.clear()
        self._channel_units.update({
            name: configured_units[index] if index < len(configured_units) else ""
            for index, name in enumerate(configured_columns)
        })
        self._adapter_headers[:] = []
        if adapter.get("x_column"):
            self._adapter_headers.append(adapter["x_column"])
        self._adapter_headers.extend(
            name for name in configured_columns if name not in self._adapter_headers
        )
        self._x_column_box.configure(values=self._adapter_headers)
        self._reload_channel_tree(self._adapter_headers, configured_columns)
        self._python_adapter_label.configure(
            text=t(csv_guidance_key(pack_name, self._python_adapter))
        )
        self._refresh_current_settings()
        for grade in "ABC":
            self._color_vars[grade].set(schema.get("GCOL", {}).get(grade, "#808080"))
        features = schema.get("features", {})
        for name, variable in self._feature_vars.items():
            variable.set(bool(features.get(name, False)))
        self._update_grade_color_state()

        edit_state = "disabled" if builtin else "normal"
        custom_reader_only = self._python_adapter and not self._adapter
        self._save_button.configure(state=edit_state)
        self._apply_field_button.configure(state=edit_state)
        self._apply_display_button.configure(state=edit_state)
        self._set_adapter_settings_state(not custom_reader_only, edit_state)
        self._readonly_label.configure(text=t("schema_editor.str6") if builtin else "")

    def _refresh_pack_list(self, select_name=None):
        names = get_pack_names()
        self._pack_list.delete(0, tk.END)
        for name in names:
            self._pack_list.insert(tk.END, name)
        self._pack_selector.configure(values=names)
        target = choose_initial_pack(
            names,
            select_name or self._current_pack.get(),
            self._settings.get("active_pack", config.DEFAULT_PACK),
        )
        index = names.index(target) if target is not None else None
        if index is not None:
            self._pack_list.selection_set(index)
            self._pack_list.activate(index)
            self._pack_list.see(index)
            self._current_pack.set(names[index])
            self._load_pack(names[index])

    def _on_pack_select(self, _event=None):
        selected = self._pack_list.curselection()
        if not selected:
            return
        name = self._pack_list.get(selected[0])
        self._current_pack.set(name)
        self._load_pack(name)

    def _on_pack_selector_select(self, _event=None):
        name = self._current_pack.get()
        names = list(self._pack_selector.cget("values"))
        if name not in names:
            return
        index = names.index(name)
        self._pack_list.selection_clear(0, tk.END)
        self._pack_list.selection_set(index)
        self._pack_list.activate(index)
        self._pack_list.see(index)
        self._load_pack(name)

    def _save_current_pack(self):
        try:
            if not self._apply_adapter_edit() or not self._apply_display_edit():
                return
            name = self._current_pack.get()
            save_user_pack(name, self._schema, self._adapter, self._viz)
            use_pack = messagebox.askyesno(
                t("schema_editor.success_title"),
                t("schema_editor.saved_use_pack", pack_name=name),
                parent=self,
            )
            if use_pack:
                self._settings.set("active_pack", name)
                messagebox.showinfo(
                    t("schema_editor.success_title"),
                    t("schema_editor.restart_to_apply"),
                    parent=self,
                )
            self._refresh_pack_list(name)
            self._notebook.select(self._tab_adapter_page)
        except Exception as error:
            messagebox.showerror(t("schema_editor.error_title"), str(error), parent=self)

    def _create_pack(self):
        name = simpledialog.askstring(
            t("schema_editor.str37"), t("schema_editor.str38"), parent=self
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
            self._refresh_pack_list(name)
            self._notebook.select(self._tab_adapter_page)
            self.after_idle(self._choose_csv_button.focus_set)
        except Exception as error:
            messagebox.showerror(t("schema_editor.error_title"), str(error), parent=self)

    def _duplicate_selected(self):
        selected = self._pack_list.curselection()
        if not selected:
            return
        source_name = self._pack_list.get(selected[0])
        name = simpledialog.askstring(
            t("schema_editor.str33"), t("schema_editor.str34"), parent=self
        )
        if not name:
            return
        try:
            destination = duplicate_pack(source_name, name)
            self._refresh_pack_list(destination.name)
            self._notebook.select(self._tab_adapter_page)
        except Exception as error:
            messagebox.showerror(t("schema_editor.error_title"), str(error), parent=self)

    def _delete_selected_pack(self):
        selected = self._pack_list.curselection()
        if not selected:
            return
        name = self._pack_list.get(selected[0])
        if name in registry:
            messagebox.showerror(
                t("schema_editor.error_title"), t("schema_editor.str30"), parent=self
            )
            return
        if not messagebox.askyesno(
            t("schema_editor.delete_title"),
            t("schema_editor.delete_confirm", pack_name=name),
            parent=self,
        ):
            return
        try:
            delete_user_pack(name)
            self._refresh_pack_list()
        except Exception as error:
            messagebox.showerror(t("schema_editor.error_title"), str(error), parent=self)

    def _initialize_sashes(self):
        """Give editors useful initial widths without overriding later user moves."""
        self.update_idletasks()
        main_width = self._main_pw.winfo_width()
        if main_width > 500:
            self._main_pw.sashpos(0, max(190, min(220, main_width // 3)))
        field_width = self._field_pw.winfo_width()
        if field_width > 420:
            self._field_pw.sashpos(
                0, max(200, min(field_width - 220, int(field_width * 0.65)))
            )


def open_schema_editor(parent):
    return SchemaEditorWindow(parent)
