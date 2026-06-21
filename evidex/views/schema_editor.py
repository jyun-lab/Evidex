"""Schema editor window for the tkinter app."""

import tkinter as tk
from tkinter import ttk

from evidex.components import Tooltip
from evidex.core import config
from evidex.core.i18n import t
from evidex.core.pack_ops import (
    adapter_mapping_layout,
    adapter_summary_lines,
    blank_adapter,
    blank_schema,
    choose_initial_pack,
    csv_guidance_key,
    save_user_pack,
)

from .schema_adapter import TkSchemaAdapterMixin
from .schema_display import TkSchemaDisplayMixin
from .schema_fields import TkSchemaFieldsMixin
from .schema_packs import TkSchemaPacksMixin

# Backward compatibility aliases for the old underscore-prefixed names
_blank_schema = blank_schema
_blank_adapter = blank_adapter


class SchemaEditorWindow(
    tk.Toplevel,
    TkSchemaFieldsMixin,
    TkSchemaAdapterMixin,
    TkSchemaDisplayMixin,
    TkSchemaPacksMixin,
):
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


def open_schema_editor(parent):
    return SchemaEditorWindow(parent)
