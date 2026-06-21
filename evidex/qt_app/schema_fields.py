"""Field editing tab logic for the schema editor dialog."""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from evidex.core.pack_ops import _PACK_NAME_RE


class SchemaFieldsMixin:
    """フィールド編集タブの UI 構築とロジック。"""

    _TYPE_LABELS = {
        "text": "テキスト",
        "number": "数値",
        "date": "日付",
        "choice": "選択肢",
    }
    _TYPE_IDS = {value: key for key, value in _TYPE_LABELS.items()}

    def _build_fields_tab(self):
        """フィールド編集タブを構築する。"""
        fields_page = QWidget()
        fields_layout = QHBoxLayout(fields_page)

        field_left = QWidget()
        fl_layout = QVBoxLayout(field_left)
        fl_layout.setContentsMargins(0, 0, 0, 0)

        self._field_table = QTableWidget()
        self._field_table.setColumnCount(5)
        self._field_table.setHorizontalHeaderLabels(
            ["ID", "日本語名", "英語名", "入力方式", "選択肢"]
        )
        self._field_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._field_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._field_table.horizontalHeader().setStretchLastSection(True)
        fl_layout.addWidget(self._field_table, stretch=1)

        field_btns = QHBoxLayout()
        self._add_field_btn = QPushButton("追加")
        self._up_field_btn = QPushButton("▲")
        self._down_field_btn = QPushButton("▼")
        self._del_field_btn = QPushButton("削除")
        field_btns.addWidget(self._add_field_btn)
        field_btns.addWidget(self._up_field_btn)
        field_btns.addWidget(self._down_field_btn)
        field_btns.addStretch()
        field_btns.addWidget(self._del_field_btn)
        fl_layout.addLayout(field_btns)
        fields_layout.addWidget(field_left, stretch=2)

        field_form = QGroupBox("フィールド編集")
        ff_layout = QFormLayout(field_form)
        self._field_id_edit = QLineEdit()
        self._field_jp_edit = QLineEdit()
        self._field_en_edit = QLineEdit()
        self._field_type_combo = QComboBox()
        self._field_type_combo.addItems(list(self._TYPE_LABELS.values()))
        self._field_choices_edit = QLineEdit()
        self._field_choices_edit.setPlaceholderText("カンマ区切り")
        self._apply_field_btn = QPushButton("適用")
        ff_layout.addRow("フィールドID:", self._field_id_edit)
        ff_layout.addRow("日本語名:", self._field_jp_edit)
        ff_layout.addRow("英語名:", self._field_en_edit)
        ff_layout.addRow("入力方式:", self._field_type_combo)
        ff_layout.addRow("選択肢:", self._field_choices_edit)
        ff_layout.addRow("", self._apply_field_btn)
        fields_layout.addWidget(field_form, stretch=1)

        self._tabs.addTab(fields_page, "フィールド")

    def _field_kind(self, field):
        if field in self._schema.get("CHOICES", {}):
            return "choice"
        return self._schema.get("FIELD_TYPES", {}).get(field, "text")

    def _reload_field_table(self, select_index=None):
        self._field_table.blockSignals(True)
        self._field_table.setRowCount(0)
        schema = self._schema
        for field in schema.get("RUN_FIELDS", []):
            choices = schema.get("CHOICES", {}).get(field, [])
            row = self._field_table.rowCount()
            self._field_table.insertRow(row)
            self._field_table.setItem(row, 0, QTableWidgetItem(field))
            self._field_table.setItem(
                row,
                1,
                QTableWidgetItem(
                    schema.get("JP_LABEL", {}).get(field, "")
                ),
            )
            self._field_table.setItem(
                row,
                2,
                QTableWidgetItem(
                    schema.get("LABEL_EN", {}).get(field, "")
                ),
            )
            self._field_table.setItem(
                row,
                3,
                QTableWidgetItem(
                    self._TYPE_LABELS.get(
                        self._field_kind(field),
                        "テキスト",
                    )
                ),
            )
            self._field_table.setItem(
                row,
                4,
                QTableWidgetItem(", ".join(choices)),
            )
        self._field_table.blockSignals(False)
        if select_index is not None and self._field_table.rowCount() > 0:
            index = max(
                0,
                min(select_index, self._field_table.rowCount() - 1),
            )
            self._field_table.selectRow(index)
            self._on_field_select()

    def _on_field_select(self):
        row = self._field_table.currentRow()
        if row < 0:
            return
        schema = self._schema
        fields = schema.get("RUN_FIELDS", [])
        if row >= len(fields):
            return
        field = fields[row]
        self._field_id_edit.setText(field)
        self._field_jp_edit.setText(
            schema.get("JP_LABEL", {}).get(field, "")
        )
        self._field_en_edit.setText(
            schema.get("LABEL_EN", {}).get(field, "")
        )
        kind = self._field_kind(field)
        self._field_type_combo.setCurrentText(
            self._TYPE_LABELS.get(kind, "テキスト")
        )
        self._field_choices_edit.setText(
            ",".join(schema.get("CHOICES", {}).get(field, []))
        )

    def _apply_field_edit(self):
        row = self._field_table.currentRow()
        if row < 0 or self._builtin:
            return
        schema = self._schema
        old_id = schema["RUN_FIELDS"][row]
        new_id = self._field_id_edit.text().strip()
        if not new_id or not _PACK_NAME_RE.fullmatch(new_id):
            QMessageBox.warning(
                self,
                "エラー",
                "フィールドIDが不正です。英数字と_-のみ使用可能。",
            )
            return
        if new_id != old_id and new_id in schema["RUN_FIELDS"]:
            QMessageBox.warning(
                self,
                "エラー",
                "同じIDのフィールドが既に存在します。",
            )
            return
        schema["RUN_FIELDS"][row] = new_id
        for key in (
            "JP_LABEL",
            "LABEL_EN",
            "FIELD_TYPES",
            "CHOICES",
        ):
            schema.setdefault(key, {})
        schema["JP_LABEL"][new_id] = self._field_jp_edit.text().strip()
        schema["LABEL_EN"][new_id] = self._field_en_edit.text().strip()
        kind = self._TYPE_IDS.get(
            self._field_type_combo.currentText(),
            "text",
        )
        schema["FIELD_TYPES"][new_id] = kind
        if kind == "choice":
            schema["CHOICES"][new_id] = [
                value.strip()
                for value in self._field_choices_edit.text().split(",")
                if value.strip()
            ]
        else:
            schema["CHOICES"].pop(new_id, None)
        if old_id != new_id:
            for key in (
                "JP_LABEL",
                "LABEL_EN",
                "FIELD_TYPES",
                "CHOICES",
            ):
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
        self._reload_field_table(row)

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
        self._reload_field_table(len(schema["RUN_FIELDS"]) - 1)

    def _delete_field(self):
        row = self._field_table.currentRow()
        if row < 0 or self._builtin:
            return
        schema = self._schema
        field = schema["RUN_FIELDS"][row]
        if field == "run_id":
            QMessageBox.warning(
                self,
                "エラー",
                "run_id は削除できません。",
            )
            return
        schema["RUN_FIELDS"].pop(row)
        for key in (
            "JP_LABEL",
            "LABEL_EN",
            "FIELD_TYPES",
            "CHOICES",
        ):
            schema.setdefault(key, {}).pop(field, None)
        schema["COLS"] = [
            item
            for item in schema.get("COLS", [])
            if item[0] != field
        ]
        schema.get("HEAD", {}).pop(field, None)
        schema["facets"] = [
            facet
            for facet in schema.get("facets", [])
            if facet.get("field") != field
        ]
        self._reload_field_table(row)

    def _move_field(self, delta):
        row = self._field_table.currentRow()
        if row < 0 or self._builtin:
            return
        fields = self._schema["RUN_FIELDS"]
        target = row + delta
        if target < 0 or target >= len(fields):
            return
        fields[row], fields[target] = fields[target], fields[row]
        self._reload_field_table(target)
