"""Adapter tab logic for the schema editor dialog."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from evidex.core.i18n import t
from evidex.core.pack_ops import adapter_summary_lines, user_pack_dir
from evidex.packs import PackInterface, registry


class SchemaAdapterMixin:
    """アダプタータブの UI 構築とロジック。"""

    def _build_adapter_tab(self):
        """アダプター設定タブを構築する。"""
        adapter_page = QScrollArea()
        adapter_page.setWidgetResizable(True)
        adapter_page.setFrameShape(QFrame.Shape.NoFrame)
        adapter_content = QWidget()
        adapter_layout = QVBoxLayout(adapter_content)

        self._current_settings_label = QLabel("")
        self._current_settings_label.setWordWrap(True)
        self._current_settings_label.setStyleSheet(
            "padding: 8px; background: #f8f8f8; border-radius: 4px;"
        )
        adapter_layout.addWidget(self._current_settings_label)

        csv_row = QHBoxLayout()
        self._choose_csv_btn = QPushButton(t("schema_editor.choose_csv"))
        self._csv_path_label = QLabel("")
        self._csv_info_label = QLabel("")
        self._csv_info_label.setStyleSheet("color: #777;")
        csv_row.addWidget(self._choose_csv_btn)
        csv_row.addWidget(self._csv_path_label, stretch=1)
        csv_row.addWidget(self._csv_info_label)
        adapter_layout.addLayout(csv_row)

        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel(t("schema_editor.str20")))
        self._skip_rows_edit = QLineEdit("0")
        self._skip_rows_edit.setFixedWidth(60)
        opt_row.addWidget(self._skip_rows_edit)
        opt_row.addWidget(QLabel(t("schema_editor.str21")))
        self._delimiter_combo = QComboBox()
        self._delimiter_combo.addItems([",", ";", "\\t"])
        self._delimiter_combo.setFixedWidth(80)
        opt_row.addWidget(self._delimiter_combo)
        self._reload_cols_btn = QPushButton(t("schema_editor.reload_columns"))
        opt_row.addWidget(self._reload_cols_btn)
        opt_row.addStretch()
        adapter_layout.addLayout(opt_row)

        self._python_adapter_note = QLabel("")
        self._python_adapter_note.setWordWrap(True)
        self._python_adapter_note.setStyleSheet("color: #555;")
        adapter_layout.addWidget(self._python_adapter_note)

        x_group = QGroupBox(t("schema_editor.x_axis_settings"))
        x_layout = QFormLayout(x_group)
        self._x_column_combo = QComboBox()
        self._x_name_edit = QLineEdit()
        self._x_unit_edit = QLineEdit()
        x_layout.addRow(t("schema_editor.str16"), self._x_column_combo)
        x_layout.addRow(t("schema_editor.x_name"), self._x_name_edit)
        x_layout.addRow(t("schema_editor.channel_unit"), self._x_unit_edit)
        adapter_layout.addWidget(x_group)

        ch_group = QGroupBox(t("schema_editor.channel_settings"))
        ch_layout = QVBoxLayout(ch_group)
        ch_layout.addWidget(
            QLabel(
                t("schema_editor.channel_help")
            )
        )

        self._channel_table = QTableWidget()
        self._channel_table.setColumnCount(3)
        self._channel_table.setHorizontalHeaderLabels([t("qt.schema.use"), t("schema_editor.channel_column"), t("schema_editor.channel_unit")])
        self._channel_table.horizontalHeader().setStretchLastSection(True)
        self._channel_table.setColumnWidth(0, 40)
        self._channel_table.setColumnWidth(1, 200)
        ch_layout.addWidget(self._channel_table, stretch=1)

        ch_btns = QHBoxLayout()
        self._ch_select_all = QPushButton(t("schema_editor.select_all"))
        self._ch_clear_all = QPushButton(t("schema_editor.clear_selection"))
        ch_btns.addWidget(self._ch_select_all)
        ch_btns.addWidget(self._ch_clear_all)

        ch_unit_row = QHBoxLayout()
        ch_unit_row.addWidget(QLabel(t("schema_editor.channel_unit")))
        self._ch_unit_edit = QLineEdit()
        self._ch_unit_edit.setFixedWidth(100)
        ch_unit_row.addWidget(self._ch_unit_edit)
        self._ch_apply_unit = QPushButton(t("btn.apply"))
        ch_unit_row.addWidget(self._ch_apply_unit)
        ch_unit_row.addStretch()
        ch_btns.addStretch()
        ch_btns.addLayout(ch_unit_row)
        ch_layout.addLayout(ch_btns)
        adapter_layout.addWidget(ch_group)

        adapter_btns = QHBoxLayout()
        self._apply_adapter_btn = QPushButton(t("schema_editor.str27"))
        self._test_adapter_btn = QPushButton(t("schema_editor.str25"))
        adapter_btns.addWidget(self._apply_adapter_btn)
        adapter_btns.addWidget(self._test_adapter_btn)
        adapter_btns.addStretch()
        adapter_layout.addLayout(adapter_btns)

        adapter_page.setWidget(adapter_content)
        self._tabs.addTab(adapter_page, t("schema_editor.str4"))

    def _delimiter_value(self):
        value = self._delimiter_combo.currentText()
        return "\t" if value == "\\t" else value

    def _delimiter_label(self, value):
        return "\\t" if value == "\t" else value

    def _parse_skip_rows(self):
        try:
            value = int(self._skip_rows_edit.text().strip() or "0")
            if value < 0:
                raise ValueError
            return value
        except ValueError:
            QMessageBox.warning(
                self,
                t("msg.error"),
                t("schema_editor.invalid_skip"),
            )
            return None

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
        self._current_settings_label.setText("\n".join(lines))

    def _reload_channel_table(self, headers, selected_names=None):
        selected_names = set(selected_names or [])
        x_column = self._x_column_combo.currentText()
        self._channel_table.setRowCount(0)
        for name in headers:
            if name == x_column:
                continue
            row = self._channel_table.rowCount()
            self._channel_table.insertRow(row)
            checkbox = QCheckBox()
            checkbox.setChecked(name in selected_names)
            self._channel_table.setCellWidget(row, 0, checkbox)
            self._channel_table.setItem(row, 1, QTableWidgetItem(name))
            self._channel_table.setItem(
                row,
                2,
                QTableWidgetItem(self._channel_units_map.get(name, "")),
            )

    def _selected_channel_names(self):
        names = []
        for row in range(self._channel_table.rowCount()):
            checkbox = self._channel_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                item = self._channel_table.item(row, 1)
                if item:
                    names.append(item.text())
        return names

    def _load_csv_columns(self, path=None, auto_detect=True):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self,
                t("schema_editor.choose_csv"),
                "",
                "CSV Files (*.csv);;All Files (*)",
            )
        if not path:
            return False
        skip = self._parse_skip_rows()
        if skip is None:
            return False
        try:
            from evidex.core.nocode_adapter import inspect_csv

            inspected = inspect_csv(
                path,
                skip_rows=skip,
                delimiter=None if auto_detect else self._delimiter_value(),
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                t("qt.msg.read_error"),
                str(error),
            )
            return False

        self._csv_path_label.setText(str(path))
        self._delimiter_combo.setCurrentText(
            self._delimiter_label(inspected["delimiter"])
        )
        self._csv_info_label.setText(
            t("qt.schema_adapter.csv_info", encoding=inspected["encoding"], columns=len(inspected["header"]))
        )
        self._adapter_headers = list(inspected["header"])
        previous_x = self._x_column_combo.currentText()
        self._x_column_combo.clear()
        self._x_column_combo.addItems(self._adapter_headers)
        if previous_x in self._adapter_headers:
            self._x_column_combo.setCurrentText(previous_x)
        elif self._adapter_headers:
            self._x_column_combo.setCurrentIndex(0)
        if not self._x_name_edit.text().strip():
            self._x_name_edit.setText(self._x_column_combo.currentText())
        configured = self._adapter or {}
        selected = [
            name
            for name in configured.get("channel_columns", [])
            if (
                name in self._adapter_headers
                and name != self._x_column_combo.currentText()
            )
        ]
        if not selected:
            selected = [
                name
                for name in self._adapter_headers
                if name != self._x_column_combo.currentText()
            ]
        self._reload_channel_table(self._adapter_headers, selected)
        return True

    def _on_x_column_changed(self):
        selected = self._selected_channel_names()
        self._reload_channel_table(self._adapter_headers, selected)
        if not self._x_name_edit.text().strip():
            self._x_name_edit.setText(self._x_column_combo.currentText())

    def _ch_toggle_all(self, checked):
        for row in range(self._channel_table.rowCount()):
            checkbox = self._channel_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(checked)

    def _apply_channel_unit(self):
        unit = self._ch_unit_edit.text().strip()
        for row in range(self._channel_table.rowCount()):
            checkbox = self._channel_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                self._channel_table.setItem(
                    row,
                    2,
                    QTableWidgetItem(unit),
                )
                name_item = self._channel_table.item(row, 1)
                if name_item:
                    self._channel_units_map[name_item.text()] = unit

    def _apply_adapter_edit(self):
        x_column = self._x_column_combo.currentText().strip()
        channels = self._selected_channel_names()
        if self._python_adapter and not x_column and not channels:
            self._adapter = None
            self._refresh_current_settings()
            return True
        if not x_column or not channels:
            QMessageBox.warning(
                self,
                t("msg.error"),
                t("schema_editor.adapter_columns_required"),
            )
            return False
        skip = self._parse_skip_rows()
        if skip is None:
            return False
        delimiter = self._delimiter_value()
        if len(delimiter) != 1:
            QMessageBox.warning(
                self,
                t("msg.error"),
                t("schema_editor.invalid_delimiter"),
            )
            return False

        channel_units = []
        for name in channels:
            for row in range(self._channel_table.rowCount()):
                name_item = self._channel_table.item(row, 1)
                if name_item and name_item.text() == name:
                    unit_item = self._channel_table.item(row, 2)
                    self._channel_units_map[name] = (
                        unit_item.text() if unit_item else ""
                    )
                    break
            channel_units.append(self._channel_units_map.get(name, ""))

        self._adapter = {
            "file_format": "csv",
            "encoding_fallback": ["utf-8-sig", "cp932"],
            "skip_rows": skip,
            "x_column": x_column,
            "x_name": self._x_name_edit.text().strip(),
            "x_unit": self._x_unit_edit.text().strip(),
            "channel_columns": channels,
            "channel_units": channel_units,
            "delimiter": delimiter,
        }
        self._refresh_current_settings()
        return True

    def _test_parse(self):
        path = self._csv_path_label.text()
        if not path and not self._load_csv_columns(auto_detect=True):
            return
        path = self._csv_path_label.text()
        if not self._apply_adapter_edit():
            return
        try:
            item = self._pack_list.currentItem()
            pack_name = item.text() if item else ""
            if self._adapter is None:
                if pack_name in registry:
                    import importlib

                    module = importlib.import_module(
                        registry[pack_name]
                    )
                    pack = PackInterface(pack_name, module=module)
                else:
                    pack = PackInterface(
                        pack_name,
                        user_path=str(user_pack_dir(pack_name)),
                    )
                signal = pack.parse(path)
            else:
                from evidex.core.nocode_adapter import (
                    parse_with_config,
                )

                signal = parse_with_config(path, self._adapter)
            QMessageBox.information(
                self,
                t("qt.msg.test_success"),
                t("qt.schema_adapter.test_success", points=len(signal.x.values), channels=len(signal.channels)),
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                t("qt.msg.test_failed"),
                str(error),
            )
