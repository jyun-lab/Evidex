import copy
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from evidex.core.i18n import t
from evidex.core.pack_ops import (
    _PACK_NAME_RE,
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
from evidex.packs import PackInterface, get_pack_names, registry


class SchemaEditorDialog(QDialog):
    """パックの作成・編集・複製・削除を行うダイアログ。"""

    _TYPE_LABELS = {
        "text": "テキスト",
        "number": "数値",
        "date": "日付",
        "choice": "選択肢",
    }
    _TYPE_IDS = {value: key for key, value in _TYPE_LABELS.items()}

    def __init__(self, parent):
        super().__init__(parent)
        from evidex.core import config, settings as app_settings

        self._config = config
        self._settings = app_settings
        self._schema = {}
        self._adapter = {}
        self._viz = {}
        self._builtin = True
        self._python_adapter = False
        self._adapter_headers = []
        self._channel_units_map = {}

        self.setWindowTitle("パック管理")
        self.resize(960, 640)
        self.setMinimumSize(680, 480)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self._build_pack_list(main_layout)
        self._build_editor_panel(main_layout)
        self._connect_signals()
        self._refresh_pack_list()

    def _build_pack_list(self, layout):
        """左パネル: パック一覧と操作ボタン。"""
        left = QWidget()
        left.setFixedWidth(200)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("パック一覧"))

        self._pack_list = QListWidget()
        self._pack_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        left_layout.addWidget(self._pack_list, stretch=1)

        btn_row1 = QHBoxLayout()
        self._new_btn = QPushButton("新規作成")
        self._dup_btn = QPushButton("複製")
        self._del_btn = QPushButton("削除")
        btn_row1.addWidget(self._new_btn)
        btn_row1.addWidget(self._dup_btn)
        btn_row1.addWidget(self._del_btn)
        left_layout.addLayout(btn_row1)

        layout.addWidget(left)

    def _build_editor_panel(self, layout):
        """右パネル: タブ付きエディタ。"""
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("編集中:"))
        self._pack_name_label = QLabel("")
        self._pack_name_label.setStyleSheet("font-weight: bold;")
        top_row.addWidget(self._pack_name_label, stretch=1)
        self._active_label = QLabel("")
        self._active_label.setStyleSheet("color: #2563EB;")
        top_row.addWidget(self._active_label)
        right_layout.addLayout(top_row)

        self._tabs = QTabWidget()
        right_layout.addWidget(self._tabs, stretch=1)

        bottom_row = QHBoxLayout()
        self._readonly_label = QLabel("")
        self._readonly_label.setStyleSheet("color: #888;")
        bottom_row.addWidget(self._readonly_label, stretch=1)
        self._save_btn = QPushButton("保存")
        self._save_btn.setEnabled(False)
        bottom_row.addWidget(self._save_btn)
        right_layout.addLayout(bottom_row)

        layout.addWidget(right, stretch=1)
        self._build_fields_tab()
        self._build_adapter_tab()
        self._build_display_tab()

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
        self._choose_csv_btn = QPushButton("CSVを選択...")
        self._csv_path_label = QLabel("")
        self._csv_info_label = QLabel("")
        self._csv_info_label.setStyleSheet("color: #777;")
        csv_row.addWidget(self._choose_csv_btn)
        csv_row.addWidget(self._csv_path_label, stretch=1)
        csv_row.addWidget(self._csv_info_label)
        adapter_layout.addLayout(csv_row)

        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel("スキップ行数:"))
        self._skip_rows_edit = QLineEdit("0")
        self._skip_rows_edit.setFixedWidth(60)
        opt_row.addWidget(self._skip_rows_edit)
        opt_row.addWidget(QLabel("区切り文字:"))
        self._delimiter_combo = QComboBox()
        self._delimiter_combo.addItems([",", ";", "\\t"])
        self._delimiter_combo.setFixedWidth(80)
        opt_row.addWidget(self._delimiter_combo)
        self._reload_cols_btn = QPushButton("列を再読込")
        opt_row.addWidget(self._reload_cols_btn)
        opt_row.addStretch()
        adapter_layout.addLayout(opt_row)

        self._python_adapter_note = QLabel("")
        self._python_adapter_note.setWordWrap(True)
        self._python_adapter_note.setStyleSheet("color: #555;")
        adapter_layout.addWidget(self._python_adapter_note)

        x_group = QGroupBox("X軸設定")
        x_layout = QFormLayout(x_group)
        self._x_column_combo = QComboBox()
        self._x_name_edit = QLineEdit()
        self._x_unit_edit = QLineEdit()
        x_layout.addRow("X軸列:", self._x_column_combo)
        x_layout.addRow("軸名:", self._x_name_edit)
        x_layout.addRow("単位:", self._x_unit_edit)
        adapter_layout.addWidget(x_group)

        ch_group = QGroupBox("チャンネル設定")
        ch_layout = QVBoxLayout(ch_group)
        ch_layout.addWidget(
            QLabel(
                "X軸列以外の列がチャンネル候補になります。"
                "チェックした列を使用します。"
            )
        )

        self._channel_table = QTableWidget()
        self._channel_table.setColumnCount(3)
        self._channel_table.setHorizontalHeaderLabels(["使用", "列名", "単位"])
        self._channel_table.horizontalHeader().setStretchLastSection(True)
        self._channel_table.setColumnWidth(0, 40)
        self._channel_table.setColumnWidth(1, 200)
        ch_layout.addWidget(self._channel_table, stretch=1)

        ch_btns = QHBoxLayout()
        self._ch_select_all = QPushButton("全選択")
        self._ch_clear_all = QPushButton("全解除")
        ch_btns.addWidget(self._ch_select_all)
        ch_btns.addWidget(self._ch_clear_all)

        ch_unit_row = QHBoxLayout()
        ch_unit_row.addWidget(QLabel("選択列の単位:"))
        self._ch_unit_edit = QLineEdit()
        self._ch_unit_edit.setFixedWidth(100)
        ch_unit_row.addWidget(self._ch_unit_edit)
        self._ch_apply_unit = QPushButton("適用")
        ch_unit_row.addWidget(self._ch_apply_unit)
        ch_unit_row.addStretch()
        ch_btns.addStretch()
        ch_btns.addLayout(ch_unit_row)
        ch_layout.addLayout(ch_btns)
        adapter_layout.addWidget(ch_group)

        adapter_btns = QHBoxLayout()
        self._apply_adapter_btn = QPushButton("設定を適用")
        self._test_adapter_btn = QPushButton("テスト読込")
        adapter_btns.addWidget(self._apply_adapter_btn)
        adapter_btns.addWidget(self._test_adapter_btn)
        adapter_btns.addStretch()
        adapter_layout.addLayout(adapter_btns)

        adapter_page.setWidget(adapter_content)
        self._tabs.addTab(adapter_page, "アダプター設定")

    def _build_display_tab(self):
        """表示設定タブを構築する。"""
        display_page = QScrollArea()
        display_page.setWidgetResizable(True)
        display_page.setFrameShape(QFrame.Shape.NoFrame)
        display_content = QWidget()
        display_layout = QVBoxLayout(display_content)

        facet_group = QGroupBox("ナビゲーション ファセット")
        facet_layout = QVBoxLayout(facet_group)
        facet_layout.addWidget(
            QLabel("ナビパネルに表示するフィールドを選択:")
        )
        self._facet_list = QListWidget()
        self._facet_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        facet_layout.addWidget(self._facet_list)
        display_layout.addWidget(facet_group)

        self._feature_group = QGroupBox("機能")
        feat_layout = QVBoxLayout(self._feature_group)
        self._feature_checks = {}
        feature_descs = {
            "steps": (
                "工程管理",
                "実験の各工程を記録・管理します",
            ),
            "series": (
                "シリーズ管理",
                "複数の実験をシリーズとしてグループ化します",
            ),
            "grading": (
                "グレード評価",
                "実験結果をA/B/Cでグレード付けします",
            ),
            "baseline": (
                "ベースライン",
                "波形のベースライン補正を有効にします",
            ),
        }
        for name, (label, description) in feature_descs.items():
            checkbox = QCheckBox(label)
            self._feature_checks[name] = checkbox
            feat_layout.addWidget(checkbox)
            desc_label = QLabel(description)
            desc_label.setStyleSheet(
                "color: #666; padding-left: 24px;"
            )
            feat_layout.addWidget(desc_label)
        display_layout.addWidget(self._feature_group)

        self._color_group = QGroupBox("Grade 色")
        color_layout = QFormLayout(self._color_group)
        self._color_edits = {}
        for grade in "ABC":
            edit = QLineEdit("#808080")
            edit.setFixedWidth(100)
            self._color_edits[grade] = edit
            color_layout.addRow(f"Grade {grade}:", edit)
        display_layout.addWidget(self._color_group)

        self._apply_display_btn = QPushButton("表示設定を適用")
        display_layout.addWidget(
            self._apply_display_btn,
            alignment=Qt.AlignmentFlag.AlignRight,
        )

        display_page.setWidget(display_content)
        self._tabs.addTab(display_page, "表示設定")

    def _connect_signals(self):
        """各ウィジェットのシグナルを接続する。"""
        self._field_table.itemSelectionChanged.connect(
            self._on_field_select
        )
        self._apply_field_btn.clicked.connect(self._apply_field_edit)
        self._add_field_btn.clicked.connect(self._add_field)
        self._del_field_btn.clicked.connect(self._delete_field)
        self._up_field_btn.clicked.connect(
            lambda: self._move_field(-1)
        )
        self._down_field_btn.clicked.connect(
            lambda: self._move_field(1)
        )
        self._choose_csv_btn.clicked.connect(
            lambda: self._load_csv_columns(auto_detect=True)
        )
        self._reload_cols_btn.clicked.connect(
            lambda: self._load_csv_columns(
                self._csv_path_label.text() or None,
                auto_detect=False,
            )
        )
        self._x_column_combo.currentTextChanged.connect(
            self._on_x_column_changed
        )
        self._ch_select_all.clicked.connect(
            lambda: self._ch_toggle_all(True)
        )
        self._ch_clear_all.clicked.connect(
            lambda: self._ch_toggle_all(False)
        )
        self._ch_apply_unit.clicked.connect(self._apply_channel_unit)
        self._apply_adapter_btn.clicked.connect(
            self._apply_adapter_edit
        )
        self._test_adapter_btn.clicked.connect(self._test_parse)
        self._apply_display_btn.clicked.connect(
            self._apply_display_edit
        )
        self._pack_list.currentItemChanged.connect(
            lambda _current, _previous: self._on_pack_select()
        )
        self._save_btn.clicked.connect(self._save_current)
        self._new_btn.clicked.connect(self._create_pack)
        self._dup_btn.clicked.connect(self._duplicate_selected)
        self._del_btn.clicked.connect(self._delete_selected)

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
                "エラー",
                "スキップ行数は0以上の整数を指定してください。",
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
                "CSVファイルを選択",
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
                "読み込みエラー",
                str(error),
            )
            return False

        self._csv_path_label.setText(str(path))
        self._delimiter_combo.setCurrentText(
            self._delimiter_label(inspected["delimiter"])
        )
        self._csv_info_label.setText(
            f"エンコーディング: {inspected['encoding']}, "
            f"列数: {len(inspected['header'])}"
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
                "エラー",
                "X軸列とチャンネル列を1つ以上選択してください。",
            )
            return False
        skip = self._parse_skip_rows()
        if skip is None:
            return False
        delimiter = self._delimiter_value()
        if len(delimiter) != 1:
            QMessageBox.warning(
                self,
                "エラー",
                "区切り文字は1文字にしてください。",
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
                "テスト成功",
                f"読込成功: {len(signal.x.values)}ポイント, "
                f"{len(signal.channels)}チャンネル",
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "テスト失敗",
                str(error),
            )

    def _reload_facets(self):
        self._facet_list.clear()
        schema = self._schema
        enabled = {
            facet.get("field")
            for facet in schema.get("facets", [])
        }
        for field in schema.get("RUN_FIELDS", []):
            label = (
                schema.get("JP_LABEL", {}).get(field)
                or schema.get("LABEL_EN", {}).get(field)
                or field
            )
            item = QListWidgetItem(f"{label}  ({field})")
            item.setData(Qt.ItemDataRole.UserRole, field)
            self._facet_list.addItem(item)
            if field in enabled:
                item.setSelected(True)

    def _apply_display_edit(self):
        import re as re_mod

        schema = self._schema
        previous = {
            facet.get("field"): facet
            for facet in schema.get("facets", [])
        }
        facets = []
        for index in range(self._facet_list.count()):
            item = self._facet_list.item(index)
            if item.isSelected():
                field = item.data(Qt.ItemDataRole.UserRole)
                facets.append(
                    previous.get(
                        field,
                        {
                            "field": field,
                            "label_key": "",
                            "source": (
                                "choices"
                                if field
                                in schema.get("CHOICES", {})
                                else "data"
                            ),
                            "match": "exact",
                        },
                    )
                )
        colors = {}
        features = {
            name: checkbox.isChecked()
            for name, checkbox in self._feature_checks.items()
        }
        if features["grading"]:
            for grade in "ABC":
                value = self._color_edits[grade].text().strip()
                if not re_mod.fullmatch(
                    r"#[0-9A-Fa-f]{6}",
                    value,
                ):
                    QMessageBox.warning(
                        self,
                        "エラー",
                        f"Grade {grade} の色が不正です。"
                        "#RRGGBB形式で入力してください。",
                    )
                    return False
                colors[grade] = value.upper()
        schema["facets"] = facets
        schema["GCOL"] = colors
        schema["features"] = features
        self._viz = {
            "facets": copy.deepcopy(facets),
            "GCOL": colors.copy(),
        }
        return True

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
                "読み込みエラー",
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
            "（アクティブ）"
            if pack_name == active_name
            else ""
        )
        self._readonly_label.setText(
            "組み込みパック（読み取り専用）"
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
                    "保存完了",
                    f"パック '{name}' を保存しました。"
                    "このパックをアクティブにしますか？",
                )
                == QMessageBox.StandardButton.Yes
            )
            if use:
                self._settings.set("active_pack", name)
                QMessageBox.information(
                    self,
                    "設定変更",
                    "再起動後に反映されます。",
                )
            self._refresh_pack_list(name)
        except Exception as error:
            QMessageBox.critical(
                self,
                "保存エラー",
                str(error),
            )

    def _create_pack(self):
        name, ok = QInputDialog.getText(
            self,
            "新規パック",
            "パック名（英数字と_-のみ）:",
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
                "作成エラー",
                str(error),
            )

    def _duplicate_selected(self):
        item = self._pack_list.currentItem()
        if not item:
            return
        source = item.text()
        name, ok = QInputDialog.getText(
            self,
            "パック複製",
            f"'{source}' のコピー名（英数字と_-のみ）:",
        )
        if not ok or not name:
            return
        try:
            destination = duplicate_pack(source, name)
            self._refresh_pack_list(destination.name)
        except Exception as error:
            QMessageBox.critical(
                self,
                "複製エラー",
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
                "エラー",
                "組み込みパックは削除できません。",
            )
            return
        if (
            QMessageBox.question(
                self,
                "削除確認",
                f"パック '{name}' を削除しますか？",
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
                "削除エラー",
                str(error),
            )


def open_schema_editor_dialog(parent):
    """パックの作成・編集・複製・削除を行うダイアログを表示する。"""
    dialog = SchemaEditorDialog(parent)
    dialog.exec()
