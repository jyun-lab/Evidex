"""Pack management logic for the schema editor dialog."""

import copy
import json

from PySide6.QtWidgets import QInputDialog, QMessageBox

from evidex.core.i18n import t
from evidex.core.pack_ops import (
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
from evidex.packs import get_pack_names, registry


class SchemaPacksMixin:
    """パック一覧の読み込み・選択・新規作成・複製・削除・保存。"""

    def _load_pack(self, pack_name):
        builtin = pack_name in registry
        try:
            if builtin:
                schema = load_schema(pack_name)
                base = pack_resource_dir(pack_name)
            else:
                base = user_pack_dir(pack_name)
                with (base / "schema.json").open(
                    "r",
                    encoding="utf-8",
                ) as handle:
                    schema = json.load(handle)
            adapter = {}
            adapter_path = base / "adapter_config.json"
            if adapter_path.is_file():
                with adapter_path.open(
                    "r",
                    encoding="utf-8",
                ) as handle:
                    adapter = json.load(handle)
            viz = {}
            viz_path = base / "viz.json"
            if viz_path.is_file():
                with viz_path.open(
                    "r",
                    encoding="utf-8",
                ) as handle:
                    viz = json.load(handle)
        except Exception as error:
            QMessageBox.critical(
                self,
                t("qt.common.read_error"),
                str(error),
            )
            return

        self._schema = copy.deepcopy(schema)
        self._adapter = copy.deepcopy(adapter)
        self._viz = copy.deepcopy(viz)
        self._builtin = builtin
        self._python_adapter = (base / "adapter.py").is_file()
        self._pack_name_label.setText(pack_name)
        active_name = self._settings.get(
            "active_pack",
            self._config.DEFAULT_PACK,
        )
        self._active_label.setText(
            t("schema_editor.active_pack_status")
            if pack_name == active_name
            else ""
        )
        self._readonly_label.setText(
            t("schema_editor.str6")
            if builtin
            else ""
        )

        self._reload_field_table(0)

        self._adapter_headers.clear()
        x_column = adapter.get("x_column", "")
        configured_columns = list(
            adapter.get("channel_columns", [])
        )
        columns = [x_column] if x_column else []
        columns.extend(
            name
            for name in configured_columns
            if name not in columns
        )
        self._adapter_headers.extend(columns)
        self._x_column_combo.clear()
        self._x_column_combo.addItems(columns)
        if x_column:
            self._x_column_combo.setCurrentText(x_column)
        self._x_name_edit.setText(str(adapter.get("x_name", "")))
        self._x_unit_edit.setText(str(adapter.get("x_unit", "")))
        self._skip_rows_edit.setText(
            str(adapter.get("skip_rows", 0))
        )
        self._delimiter_combo.setCurrentText(
            self._delimiter_label(adapter.get("delimiter", ","))
        )
        self._csv_path_label.setText("")
        self._csv_info_label.setText("")
        self._channel_units_map.clear()
        configured_units = list(
            adapter.get("channel_units", [])
        )
        self._channel_units_map.update(
            {
                name: (
                    configured_units[index]
                    if index < len(configured_units)
                    else ""
                )
                for index, name in enumerate(configured_columns)
            }
        )
        self._reload_channel_table(
            self._adapter_headers,
            configured_columns,
        )
        self._python_adapter_note.setText(
            t(
                csv_guidance_key(
                    pack_name,
                    self._python_adapter,
                )
            )
        )
        self._refresh_current_settings()

        for grade in "ABC":
            self._color_edits[grade].setText(
                schema.get("GCOL", {}).get(
                    grade,
                    "#808080",
                )
            )
        features = schema.get("features", {})
        for name, checkbox in self._feature_checks.items():
            checkbox.setChecked(
                bool(features.get(name, False))
            )
        self._reload_facets()

        editable = not builtin
        self._save_btn.setEnabled(editable)
        self._apply_field_btn.setEnabled(editable)
        self._apply_display_btn.setEnabled(editable)
        self._add_field_btn.setEnabled(editable)
        self._del_field_btn.setEnabled(editable)
        self._up_field_btn.setEnabled(editable)
        self._down_field_btn.setEnabled(editable)
        self._apply_adapter_btn.setEnabled(editable)
        self._test_adapter_btn.setEnabled(editable)
        self._choose_csv_btn.setEnabled(editable)
        self._reload_cols_btn.setEnabled(editable)
        self._ch_select_all.setEnabled(editable)
        self._ch_clear_all.setEnabled(editable)
        self._ch_apply_unit.setEnabled(editable)
        self._del_btn.setEnabled(editable)
        self._field_id_edit.setReadOnly(not editable)
        self._field_jp_edit.setReadOnly(not editable)
        self._field_en_edit.setReadOnly(not editable)
        self._field_type_combo.setEnabled(editable)
        self._field_choices_edit.setReadOnly(not editable)
        self._skip_rows_edit.setReadOnly(not editable)
        self._delimiter_combo.setEnabled(editable)
        self._x_column_combo.setEnabled(editable)
        self._x_name_edit.setReadOnly(not editable)
        self._x_unit_edit.setReadOnly(not editable)
        self._ch_unit_edit.setReadOnly(not editable)
        self._facet_list.setEnabled(editable)
        self._feature_group.setEnabled(editable)
        self._color_group.setEnabled(editable)

    def _refresh_pack_list(self, select_name=None):
        names = get_pack_names()
        selected_item = self._pack_list.currentItem()
        previous_name = (
            selected_item.text() if selected_item else ""
        )
        self._pack_list.blockSignals(True)
        self._pack_list.clear()
        self._pack_list.addItems(names)
        target = choose_initial_pack(
            names,
            select_name or previous_name,
            self._settings.get(
                "active_pack",
                self._config.DEFAULT_PACK,
            ),
        )
        if target and target in names:
            self._pack_list.setCurrentRow(names.index(target))
        self._pack_list.blockSignals(False)
        if target:
            self._load_pack(target)

    def _on_pack_select(self):
        item = self._pack_list.currentItem()
        if item:
            self._load_pack(item.text())

    def _save_current(self):
        try:
            if not self._apply_adapter_edit() or not self._apply_display_edit():
                return
            item = self._pack_list.currentItem()
            if not item:
                return
            name = item.text()
            validate_schema(self._schema)
            save_user_pack(
                name,
                self._schema,
                self._adapter,
                self._viz,
            )
            use = (
                QMessageBox.question(
                    self,
                    t("schema_editor.success_title"),
                    t("schema_editor.saved_use_pack", pack_name=name),
                )
                == QMessageBox.StandardButton.Yes
            )
            if use:
                self._settings.set("active_pack", name)
                QMessageBox.information(
                    self,
                    t("qt.common.settings_changed"),
                    t("schema_editor.restart_to_apply"),
                )
            self._refresh_pack_list(name)
        except Exception as error:
            QMessageBox.critical(
                self,
                t("data.msg.save_error"),
                str(error),
            )

    def _create_pack(self):
        name, ok = QInputDialog.getText(
            self,
            t("schema_editor.str37"),
            t("schema_editor.str38"),
        )
        if not ok or not name:
            return
        try:
            name = validate_pack_name(name)
            schema = blank_schema()
            save_user_pack(
                name,
                schema,
                blank_adapter(),
                {
                    "facets": [],
                    "GCOL": schema["GCOL"].copy(),
                },
            )
            self._refresh_pack_list(name)
        except Exception as error:
            QMessageBox.critical(
                self,
                t("qt.common.create_error"),
                str(error),
            )

    def _duplicate_selected(self):
        item = self._pack_list.currentItem()
        if not item:
            return
        source = item.text()
        name, ok = QInputDialog.getText(
            self,
            t("schema_editor.str33"),
            t("qt.schema_packs.copy_name_prompt", source=source),
        )
        if not ok or not name:
            return
        try:
            destination = duplicate_pack(source, name)
            self._refresh_pack_list(destination.name)
        except Exception as error:
            QMessageBox.critical(
                self,
                t("qt.common.duplicate_error"),
                str(error),
            )

    def _delete_selected(self):
        item = self._pack_list.currentItem()
        if not item:
            return
        name = item.text()
        if name in registry:
            QMessageBox.warning(
                self,
                t("msg.error"),
                t("schema_editor.str30"),
            )
            return
        if (
            QMessageBox.question(
                self,
                t("schema_editor.delete_title"),
                t("schema_editor.delete_confirm", pack_name=name),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            delete_user_pack(name)
            self._refresh_pack_list()
        except Exception as error:
            QMessageBox.critical(
                self,
                t("qt.common.delete_error"),
                str(error),
            )
