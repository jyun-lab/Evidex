"""Adapter tab logic for the tkinter schema editor."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from evidex.components import Tooltip
from evidex.core.i18n import t
from evidex.core.pack_ops import (
    adapter_mapping_layout,
    adapter_summary_lines,
    user_pack_dir,
)
from evidex.core.table_style import configure_treeview_rows, stripe_tag
from evidex.packs import PackInterface, registry


class TkSchemaAdapterMixin:
    """アダプタータブの UI 構築とロジック。"""

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
