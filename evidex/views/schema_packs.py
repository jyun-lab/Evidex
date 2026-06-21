"""Pack management logic for the tkinter schema editor."""

import copy
import json
import tkinter as tk
from tkinter import messagebox, simpledialog

from evidex.core import config
from evidex.core.i18n import t
from evidex.core.pack_ops import (
    choose_initial_pack,
    csv_guidance_key,
    delete_user_pack,
    duplicate_pack,
    save_user_pack,
    user_pack_dir,
    validate_pack_name,
)
from evidex.core.schema import load_schema, pack_resource_dir
from evidex.packs import get_pack_names, registry


class TkSchemaPacksMixin:
    """パック一覧の読み込み・選択・新規作成・複製・削除・保存。"""

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
