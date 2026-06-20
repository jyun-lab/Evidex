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


def open_schema_editor_dialog(parent):
    """パックの作成・編集・複製・削除を行うダイアログを表示する。"""
    from evidex.core import config, settings

    dialog = QDialog(parent)
    dialog.setWindowTitle("パック管理")
    dialog.resize(960, 640)
    dialog.setMinimumSize(680, 480)

    main_layout = QHBoxLayout(dialog)
    main_layout.setContentsMargins(10, 10, 10, 10)
    main_layout.setSpacing(10)

    state = {
        "schema": {},
        "adapter": {},
        "viz": {},
        "builtin": True,
        "python_adapter": False,
    }

    # ── 左パネル: パック一覧 ──
    left = QWidget()
    left.setFixedWidth(200)
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(0, 0, 0, 0)

    left_layout.addWidget(QLabel("パック一覧"))

    pack_list = QListWidget()
    pack_list.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
    )
    left_layout.addWidget(pack_list, stretch=1)

    btn_row1 = QHBoxLayout()
    new_btn = QPushButton("新規作成")
    dup_btn = QPushButton("複製")
    del_btn = QPushButton("削除")
    btn_row1.addWidget(new_btn)
    btn_row1.addWidget(dup_btn)
    btn_row1.addWidget(del_btn)
    left_layout.addLayout(btn_row1)

    main_layout.addWidget(left)

    # ── 右パネル: タブ付きエディタ ──
    right = QWidget()
    right_layout = QVBoxLayout(right)
    right_layout.setContentsMargins(0, 0, 0, 0)

    top_row = QHBoxLayout()
    top_row.addWidget(QLabel("編集中:"))
    pack_name_label = QLabel("")
    pack_name_label.setStyleSheet("font-weight: bold;")
    top_row.addWidget(pack_name_label, stretch=1)
    active_label = QLabel("")
    active_label.setStyleSheet("color: #2563EB;")
    top_row.addWidget(active_label)
    right_layout.addLayout(top_row)

    tabs = QTabWidget()
    right_layout.addWidget(tabs, stretch=1)

    bottom_row = QHBoxLayout()
    readonly_label = QLabel("")
    readonly_label.setStyleSheet("color: #888;")
    bottom_row.addWidget(readonly_label, stretch=1)
    save_btn = QPushButton("保存")
    save_btn.setEnabled(False)
    bottom_row.addWidget(save_btn)
    right_layout.addLayout(bottom_row)

    main_layout.addWidget(right, stretch=1)

    # ── タブ1: フィールド ──
    fields_page = QWidget()
    fields_layout = QHBoxLayout(fields_page)

    field_left = QWidget()
    fl_layout = QVBoxLayout(field_left)
    fl_layout.setContentsMargins(0, 0, 0, 0)

    field_table = QTableWidget()
    field_table.setColumnCount(5)
    field_table.setHorizontalHeaderLabels(
        ["ID", "日本語名", "英語名", "入力方式", "選択肢"]
    )
    field_table.setSelectionBehavior(
        QAbstractItemView.SelectionBehavior.SelectRows
    )
    field_table.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
    )
    field_table.horizontalHeader().setStretchLastSection(True)
    fl_layout.addWidget(field_table, stretch=1)

    field_btns = QHBoxLayout()
    add_field_btn = QPushButton("追加")
    up_field_btn = QPushButton("▲")
    down_field_btn = QPushButton("▼")
    del_field_btn = QPushButton("削除")
    field_btns.addWidget(add_field_btn)
    field_btns.addWidget(up_field_btn)
    field_btns.addWidget(down_field_btn)
    field_btns.addStretch()
    field_btns.addWidget(del_field_btn)
    fl_layout.addLayout(field_btns)
    fields_layout.addWidget(field_left, stretch=2)

    field_form = QGroupBox("フィールド編集")
    ff_layout = QFormLayout(field_form)
    field_id_edit = QLineEdit()
    field_jp_edit = QLineEdit()
    field_en_edit = QLineEdit()
    type_labels = {
        "text": "テキスト",
        "number": "数値",
        "date": "日付",
        "choice": "選択肢",
    }
    type_ids = {value: key for key, value in type_labels.items()}
    field_type_combo = QComboBox()
    field_type_combo.addItems(list(type_labels.values()))
    field_choices_edit = QLineEdit()
    field_choices_edit.setPlaceholderText("カンマ区切り")
    apply_field_btn = QPushButton("適用")
    ff_layout.addRow("フィールドID:", field_id_edit)
    ff_layout.addRow("日本語名:", field_jp_edit)
    ff_layout.addRow("英語名:", field_en_edit)
    ff_layout.addRow("入力方式:", field_type_combo)
    ff_layout.addRow("選択肢:", field_choices_edit)
    ff_layout.addRow("", apply_field_btn)
    fields_layout.addWidget(field_form, stretch=1)

    tabs.addTab(fields_page, "フィールド")

    def field_kind(schema, field):
        if field in schema.get("CHOICES", {}):
            return "choice"
        return schema.get("FIELD_TYPES", {}).get(field, "text")

    def reload_field_table(select_index=None):
        field_table.blockSignals(True)
        field_table.setRowCount(0)
        schema = state["schema"]
        for field in schema.get("RUN_FIELDS", []):
            choices = schema.get("CHOICES", {}).get(field, [])
            row = field_table.rowCount()
            field_table.insertRow(row)
            field_table.setItem(row, 0, QTableWidgetItem(field))
            field_table.setItem(
                row,
                1,
                QTableWidgetItem(
                    schema.get("JP_LABEL", {}).get(field, "")
                ),
            )
            field_table.setItem(
                row,
                2,
                QTableWidgetItem(
                    schema.get("LABEL_EN", {}).get(field, "")
                ),
            )
            field_table.setItem(
                row,
                3,
                QTableWidgetItem(
                    type_labels.get(
                        field_kind(schema, field),
                        "テキスト",
                    )
                ),
            )
            field_table.setItem(
                row,
                4,
                QTableWidgetItem(", ".join(choices)),
            )
        field_table.blockSignals(False)
        if select_index is not None and field_table.rowCount() > 0:
            index = max(
                0,
                min(select_index, field_table.rowCount() - 1),
            )
            field_table.selectRow(index)
            on_field_select()

    def on_field_select():
        row = field_table.currentRow()
        if row < 0:
            return
        schema = state["schema"]
        fields = schema.get("RUN_FIELDS", [])
        if row >= len(fields):
            return
        field = fields[row]
        field_id_edit.setText(field)
        field_jp_edit.setText(
            schema.get("JP_LABEL", {}).get(field, "")
        )
        field_en_edit.setText(
            schema.get("LABEL_EN", {}).get(field, "")
        )
        kind = field_kind(schema, field)
        field_type_combo.setCurrentText(
            type_labels.get(kind, "テキスト")
        )
        field_choices_edit.setText(
            ",".join(schema.get("CHOICES", {}).get(field, []))
        )

    field_table.itemSelectionChanged.connect(on_field_select)

    def apply_field_edit():
        row = field_table.currentRow()
        if row < 0 or state["builtin"]:
            return
        schema = state["schema"]
        old_id = schema["RUN_FIELDS"][row]
        new_id = field_id_edit.text().strip()
        if not new_id or not _PACK_NAME_RE.fullmatch(new_id):
            QMessageBox.warning(
                dialog,
                "エラー",
                "フィールドIDが不正です。英数字と_-のみ使用可能。",
            )
            return
        if new_id != old_id and new_id in schema["RUN_FIELDS"]:
            QMessageBox.warning(
                dialog,
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
        schema["JP_LABEL"][new_id] = field_jp_edit.text().strip()
        schema["LABEL_EN"][new_id] = field_en_edit.text().strip()
        kind = type_ids.get(
            field_type_combo.currentText(),
            "text",
        )
        schema["FIELD_TYPES"][new_id] = kind
        if kind == "choice":
            schema["CHOICES"][new_id] = [
                value.strip()
                for value in field_choices_edit.text().split(",")
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
        reload_field_table(row)

    apply_field_btn.clicked.connect(apply_field_edit)

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
        reload_field_table(len(schema["RUN_FIELDS"]) - 1)

    def delete_field():
        row = field_table.currentRow()
        if row < 0 or state["builtin"]:
            return
        schema = state["schema"]
        field = schema["RUN_FIELDS"][row]
        if field == "run_id":
            QMessageBox.warning(
                dialog,
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
        reload_field_table(row)

    def move_field(delta):
        row = field_table.currentRow()
        if row < 0 or state["builtin"]:
            return
        fields = state["schema"]["RUN_FIELDS"]
        target = row + delta
        if target < 0 or target >= len(fields):
            return
        fields[row], fields[target] = fields[target], fields[row]
        reload_field_table(target)

    add_field_btn.clicked.connect(add_field)
    del_field_btn.clicked.connect(delete_field)
    up_field_btn.clicked.connect(lambda: move_field(-1))
    down_field_btn.clicked.connect(lambda: move_field(1))

    # ── タブ2: アダプター設定 ──
    adapter_page = QScrollArea()
    adapter_page.setWidgetResizable(True)
    adapter_page.setFrameShape(QFrame.Shape.NoFrame)
    adapter_content = QWidget()
    adapter_layout = QVBoxLayout(adapter_content)

    current_settings_label = QLabel("")
    current_settings_label.setWordWrap(True)
    current_settings_label.setStyleSheet(
        "padding: 8px; background: #f8f8f8; border-radius: 4px;"
    )
    adapter_layout.addWidget(current_settings_label)

    csv_row = QHBoxLayout()
    choose_csv_btn = QPushButton("CSVを選択...")
    csv_path_label = QLabel("")
    csv_info_label = QLabel("")
    csv_info_label.setStyleSheet("color: #777;")
    csv_row.addWidget(choose_csv_btn)
    csv_row.addWidget(csv_path_label, stretch=1)
    csv_row.addWidget(csv_info_label)
    adapter_layout.addLayout(csv_row)

    opt_row = QHBoxLayout()
    opt_row.addWidget(QLabel("スキップ行数:"))
    skip_rows_edit = QLineEdit("0")
    skip_rows_edit.setFixedWidth(60)
    opt_row.addWidget(skip_rows_edit)
    opt_row.addWidget(QLabel("区切り文字:"))
    delimiter_combo = QComboBox()
    delimiter_combo.addItems([",", ";", "\\t"])
    delimiter_combo.setFixedWidth(80)
    opt_row.addWidget(delimiter_combo)
    reload_cols_btn = QPushButton("列を再読込")
    opt_row.addWidget(reload_cols_btn)
    opt_row.addStretch()
    adapter_layout.addLayout(opt_row)

    python_adapter_note = QLabel("")
    python_adapter_note.setWordWrap(True)
    python_adapter_note.setStyleSheet("color: #555;")
    adapter_layout.addWidget(python_adapter_note)

    x_group = QGroupBox("X軸設定")
    x_layout = QFormLayout(x_group)
    x_column_combo = QComboBox()
    x_name_edit = QLineEdit()
    x_unit_edit = QLineEdit()
    x_layout.addRow("X軸列:", x_column_combo)
    x_layout.addRow("軸名:", x_name_edit)
    x_layout.addRow("単位:", x_unit_edit)
    adapter_layout.addWidget(x_group)

    ch_group = QGroupBox("チャンネル設定")
    ch_layout = QVBoxLayout(ch_group)
    ch_layout.addWidget(
        QLabel(
            "X軸列以外の列がチャンネル候補になります。"
            "チェックした列を使用します。"
        )
    )

    channel_table = QTableWidget()
    channel_table.setColumnCount(3)
    channel_table.setHorizontalHeaderLabels(["使用", "列名", "単位"])
    channel_table.horizontalHeader().setStretchLastSection(True)
    channel_table.setColumnWidth(0, 40)
    channel_table.setColumnWidth(1, 200)
    ch_layout.addWidget(channel_table, stretch=1)

    ch_btns = QHBoxLayout()
    ch_select_all = QPushButton("全選択")
    ch_clear_all = QPushButton("全解除")
    ch_btns.addWidget(ch_select_all)
    ch_btns.addWidget(ch_clear_all)

    ch_unit_row = QHBoxLayout()
    ch_unit_row.addWidget(QLabel("選択列の単位:"))
    ch_unit_edit = QLineEdit()
    ch_unit_edit.setFixedWidth(100)
    ch_unit_row.addWidget(ch_unit_edit)
    ch_apply_unit = QPushButton("適用")
    ch_unit_row.addWidget(ch_apply_unit)
    ch_unit_row.addStretch()
    ch_btns.addStretch()
    ch_btns.addLayout(ch_unit_row)
    ch_layout.addLayout(ch_btns)
    adapter_layout.addWidget(ch_group)

    adapter_btns = QHBoxLayout()
    apply_adapter_btn = QPushButton("設定を適用")
    test_adapter_btn = QPushButton("テスト読込")
    adapter_btns.addWidget(apply_adapter_btn)
    adapter_btns.addWidget(test_adapter_btn)
    adapter_btns.addStretch()
    adapter_layout.addLayout(adapter_btns)

    adapter_page.setWidget(adapter_content)
    tabs.addTab(adapter_page, "アダプター設定")

    adapter_headers = []
    channel_units_map = {}

    def delimiter_value():
        value = delimiter_combo.currentText()
        return "\t" if value == "\\t" else value

    def delimiter_label(value):
        return "\\t" if value == "\t" else value

    def parse_skip_rows():
        try:
            value = int(skip_rows_edit.text().strip() or "0")
            if value < 0:
                raise ValueError
            return value
        except ValueError:
            QMessageBox.warning(
                dialog,
                "エラー",
                "スキップ行数は0以上の整数を指定してください。",
            )
            return None

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
        current_settings_label.setText("\n".join(lines))

    def reload_channel_table(headers, selected_names=None):
        selected_names = set(selected_names or [])
        x_column = x_column_combo.currentText()
        channel_table.setRowCount(0)
        for name in headers:
            if name == x_column:
                continue
            row = channel_table.rowCount()
            channel_table.insertRow(row)
            checkbox = QCheckBox()
            checkbox.setChecked(name in selected_names)
            channel_table.setCellWidget(row, 0, checkbox)
            channel_table.setItem(row, 1, QTableWidgetItem(name))
            channel_table.setItem(
                row,
                2,
                QTableWidgetItem(channel_units_map.get(name, "")),
            )

    def selected_channel_names():
        names = []
        for row in range(channel_table.rowCount()):
            checkbox = channel_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                item = channel_table.item(row, 1)
                if item:
                    names.append(item.text())
        return names

    def load_csv_columns(path=None, auto_detect=True):
        nonlocal adapter_headers
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                dialog,
                "CSVファイルを選択",
                "",
                "CSV Files (*.csv);;All Files (*)",
            )
        if not path:
            return False
        skip = parse_skip_rows()
        if skip is None:
            return False
        try:
            from evidex.core.nocode_adapter import inspect_csv

            inspected = inspect_csv(
                path,
                skip_rows=skip,
                delimiter=None if auto_detect else delimiter_value(),
            )
        except Exception as error:
            QMessageBox.critical(
                dialog,
                "読み込みエラー",
                str(error),
            )
            return False

        csv_path_label.setText(str(path))
        delimiter_combo.setCurrentText(
            delimiter_label(inspected["delimiter"])
        )
        csv_info_label.setText(
            f"エンコーディング: {inspected['encoding']}, "
            f"列数: {len(inspected['header'])}"
        )
        adapter_headers = list(inspected["header"])
        previous_x = x_column_combo.currentText()
        x_column_combo.clear()
        x_column_combo.addItems(adapter_headers)
        if previous_x in adapter_headers:
            x_column_combo.setCurrentText(previous_x)
        elif adapter_headers:
            x_column_combo.setCurrentIndex(0)
        if not x_name_edit.text().strip():
            x_name_edit.setText(x_column_combo.currentText())
        configured = state.get("adapter") or {}
        selected = [
            name
            for name in configured.get("channel_columns", [])
            if (
                name in adapter_headers
                and name != x_column_combo.currentText()
            )
        ]
        if not selected:
            selected = [
                name
                for name in adapter_headers
                if name != x_column_combo.currentText()
            ]
        reload_channel_table(adapter_headers, selected)
        return True

    choose_csv_btn.clicked.connect(
        lambda: load_csv_columns(auto_detect=True)
    )
    reload_cols_btn.clicked.connect(
        lambda: load_csv_columns(
            csv_path_label.text() or None,
            auto_detect=False,
        )
    )

    def on_x_column_changed():
        selected = selected_channel_names()
        reload_channel_table(adapter_headers, selected)
        if not x_name_edit.text().strip():
            x_name_edit.setText(x_column_combo.currentText())

    x_column_combo.currentTextChanged.connect(on_x_column_changed)

    def ch_toggle_all(checked):
        for row in range(channel_table.rowCount()):
            checkbox = channel_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(checked)

    ch_select_all.clicked.connect(lambda: ch_toggle_all(True))
    ch_clear_all.clicked.connect(lambda: ch_toggle_all(False))

    def apply_channel_unit():
        unit = ch_unit_edit.text().strip()
        for row in range(channel_table.rowCount()):
            checkbox = channel_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                channel_table.setItem(
                    row,
                    2,
                    QTableWidgetItem(unit),
                )
                name_item = channel_table.item(row, 1)
                if name_item:
                    channel_units_map[name_item.text()] = unit

    ch_apply_unit.clicked.connect(apply_channel_unit)

    def apply_adapter_edit():
        x_column = x_column_combo.currentText().strip()
        channels = selected_channel_names()
        if state["python_adapter"] and not x_column and not channels:
            state["adapter"] = None
            refresh_current_settings()
            return True
        if not x_column or not channels:
            QMessageBox.warning(
                dialog,
                "エラー",
                "X軸列とチャンネル列を1つ以上選択してください。",
            )
            return False
        skip = parse_skip_rows()
        if skip is None:
            return False
        delimiter = delimiter_value()
        if len(delimiter) != 1:
            QMessageBox.warning(
                dialog,
                "エラー",
                "区切り文字は1文字にしてください。",
            )
            return False

        channel_units = []
        for name in channels:
            for row in range(channel_table.rowCount()):
                name_item = channel_table.item(row, 1)
                if name_item and name_item.text() == name:
                    unit_item = channel_table.item(row, 2)
                    channel_units_map[name] = (
                        unit_item.text() if unit_item else ""
                    )
                    break
            channel_units.append(channel_units_map.get(name, ""))

        state["adapter"] = {
            "file_format": "csv",
            "encoding_fallback": ["utf-8-sig", "cp932"],
            "skip_rows": skip,
            "x_column": x_column,
            "x_name": x_name_edit.text().strip(),
            "x_unit": x_unit_edit.text().strip(),
            "channel_columns": channels,
            "channel_units": channel_units,
            "delimiter": delimiter,
        }
        refresh_current_settings()
        return True

    apply_adapter_btn.clicked.connect(apply_adapter_edit)

    def test_parse():
        path = csv_path_label.text()
        if not path and not load_csv_columns(auto_detect=True):
            return
        path = csv_path_label.text()
        if not apply_adapter_edit():
            return
        try:
            item = pack_list.currentItem()
            pack_name = item.text() if item else ""
            if state["adapter"] is None:
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

                signal = parse_with_config(path, state["adapter"])
            QMessageBox.information(
                dialog,
                "テスト成功",
                f"読込成功: {len(signal.x.values)}ポイント, "
                f"{len(signal.channels)}チャンネル",
            )
        except Exception as error:
            QMessageBox.critical(
                dialog,
                "テスト失敗",
                str(error),
            )

    test_adapter_btn.clicked.connect(test_parse)

    # ── タブ3: 表示設定 ──
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
    facet_list = QListWidget()
    facet_list.setSelectionMode(
        QAbstractItemView.SelectionMode.MultiSelection
    )
    facet_layout.addWidget(facet_list)
    display_layout.addWidget(facet_group)

    feature_group = QGroupBox("機能")
    feat_layout = QVBoxLayout(feature_group)
    feature_checks = {}
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
        feature_checks[name] = checkbox
        feat_layout.addWidget(checkbox)
        desc_label = QLabel(description)
        desc_label.setStyleSheet(
            "color: #666; padding-left: 24px;"
        )
        feat_layout.addWidget(desc_label)
    display_layout.addWidget(feature_group)

    color_group = QGroupBox("Grade 色")
    color_layout = QFormLayout(color_group)
    color_edits = {}
    for grade in "ABC":
        edit = QLineEdit("#808080")
        edit.setFixedWidth(100)
        color_edits[grade] = edit
        color_layout.addRow(f"Grade {grade}:", edit)
    display_layout.addWidget(color_group)

    apply_display_btn = QPushButton("表示設定を適用")
    display_layout.addWidget(
        apply_display_btn,
        alignment=Qt.AlignmentFlag.AlignRight,
    )

    display_page.setWidget(display_content)
    tabs.addTab(display_page, "表示設定")

    def reload_facets():
        facet_list.clear()
        schema = state["schema"]
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
            facet_list.addItem(item)
            if field in enabled:
                item.setSelected(True)

    def apply_display_edit():
        import re as re_mod

        schema = state["schema"]
        previous = {
            facet.get("field"): facet
            for facet in schema.get("facets", [])
        }
        facets = []
        for index in range(facet_list.count()):
            item = facet_list.item(index)
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
            for name, checkbox in feature_checks.items()
        }
        if features["grading"]:
            for grade in "ABC":
                value = color_edits[grade].text().strip()
                if not re_mod.fullmatch(
                    r"#[0-9A-Fa-f]{6}",
                    value,
                ):
                    QMessageBox.warning(
                        dialog,
                        "エラー",
                        f"Grade {grade} の色が不正です。"
                        "#RRGGBB形式で入力してください。",
                    )
                    return False
                colors[grade] = value.upper()
        schema["facets"] = facets
        schema["GCOL"] = colors
        schema["features"] = features
        state["viz"] = {
            "facets": copy.deepcopy(facets),
            "GCOL": colors.copy(),
        }
        return True

    apply_display_btn.clicked.connect(apply_display_edit)

    # ── パック読み込み・保存・作成・複製・削除 ──
    def load_pack(pack_name):
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
                dialog,
                "読み込みエラー",
                str(error),
            )
            return

        state.update(
            schema=copy.deepcopy(schema),
            adapter=copy.deepcopy(adapter),
            viz=copy.deepcopy(viz),
            builtin=builtin,
            python_adapter=(base / "adapter.py").is_file(),
        )
        pack_name_label.setText(pack_name)
        active_name = settings.get(
            "active_pack",
            config.DEFAULT_PACK,
        )
        active_label.setText(
            "（アクティブ）"
            if pack_name == active_name
            else ""
        )
        readonly_label.setText(
            "組み込みパック（読み取り専用）"
            if builtin
            else ""
        )

        reload_field_table(0)

        adapter_headers.clear()
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
        adapter_headers.extend(columns)
        x_column_combo.clear()
        x_column_combo.addItems(columns)
        if x_column:
            x_column_combo.setCurrentText(x_column)
        x_name_edit.setText(str(adapter.get("x_name", "")))
        x_unit_edit.setText(str(adapter.get("x_unit", "")))
        skip_rows_edit.setText(
            str(adapter.get("skip_rows", 0))
        )
        delimiter_combo.setCurrentText(
            delimiter_label(adapter.get("delimiter", ","))
        )
        csv_path_label.setText("")
        csv_info_label.setText("")
        channel_units_map.clear()
        configured_units = list(
            adapter.get("channel_units", [])
        )
        channel_units_map.update(
            {
                name: (
                    configured_units[index]
                    if index < len(configured_units)
                    else ""
                )
                for index, name in enumerate(configured_columns)
            }
        )
        reload_channel_table(
            adapter_headers,
            configured_columns,
        )
        python_adapter_note.setText(
            t(
                csv_guidance_key(
                    pack_name,
                    state["python_adapter"],
                )
            )
        )
        refresh_current_settings()

        for grade in "ABC":
            color_edits[grade].setText(
                schema.get("GCOL", {}).get(
                    grade,
                    "#808080",
                )
            )
        features = schema.get("features", {})
        for name, checkbox in feature_checks.items():
            checkbox.setChecked(
                bool(features.get(name, False))
            )
        reload_facets()

        editable = not builtin
        save_btn.setEnabled(editable)
        apply_field_btn.setEnabled(editable)
        apply_display_btn.setEnabled(editable)
        add_field_btn.setEnabled(editable)
        del_field_btn.setEnabled(editable)
        up_field_btn.setEnabled(editable)
        down_field_btn.setEnabled(editable)
        apply_adapter_btn.setEnabled(editable)
        test_adapter_btn.setEnabled(editable)
        choose_csv_btn.setEnabled(editable)
        reload_cols_btn.setEnabled(editable)
        ch_select_all.setEnabled(editable)
        ch_clear_all.setEnabled(editable)
        ch_apply_unit.setEnabled(editable)
        del_btn.setEnabled(editable)
        field_id_edit.setReadOnly(not editable)
        field_jp_edit.setReadOnly(not editable)
        field_en_edit.setReadOnly(not editable)
        field_type_combo.setEnabled(editable)
        field_choices_edit.setReadOnly(not editable)
        skip_rows_edit.setReadOnly(not editable)
        delimiter_combo.setEnabled(editable)
        x_column_combo.setEnabled(editable)
        x_name_edit.setReadOnly(not editable)
        x_unit_edit.setReadOnly(not editable)
        ch_unit_edit.setReadOnly(not editable)
        facet_list.setEnabled(editable)
        feature_group.setEnabled(editable)
        color_group.setEnabled(editable)

    def refresh_pack_list(select_name=None):
        names = get_pack_names()
        selected_item = pack_list.currentItem()
        previous_name = (
            selected_item.text() if selected_item else ""
        )
        pack_list.blockSignals(True)
        pack_list.clear()
        pack_list.addItems(names)
        target = choose_initial_pack(
            names,
            select_name or previous_name,
            settings.get(
                "active_pack",
                config.DEFAULT_PACK,
            ),
        )
        if target and target in names:
            pack_list.setCurrentRow(names.index(target))
        pack_list.blockSignals(False)
        if target:
            load_pack(target)

    def on_pack_select():
        item = pack_list.currentItem()
        if item:
            load_pack(item.text())

    pack_list.currentItemChanged.connect(
        lambda _current, _previous: on_pack_select()
    )

    def save_current():
        try:
            if not apply_adapter_edit() or not apply_display_edit():
                return
            item = pack_list.currentItem()
            if not item:
                return
            name = item.text()
            validate_schema(state["schema"])
            save_user_pack(
                name,
                state["schema"],
                state["adapter"],
                state["viz"],
            )
            use = (
                QMessageBox.question(
                    dialog,
                    "保存完了",
                    f"パック '{name}' を保存しました。"
                    "このパックをアクティブにしますか？",
                )
                == QMessageBox.StandardButton.Yes
            )
            if use:
                settings.set("active_pack", name)
                QMessageBox.information(
                    dialog,
                    "設定変更",
                    "再起動後に反映されます。",
                )
            refresh_pack_list(name)
        except Exception as error:
            QMessageBox.critical(
                dialog,
                "保存エラー",
                str(error),
            )

    save_btn.clicked.connect(save_current)

    def create_pack():
        name, ok = QInputDialog.getText(
            dialog,
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
            refresh_pack_list(name)
        except Exception as error:
            QMessageBox.critical(
                dialog,
                "作成エラー",
                str(error),
            )

    def duplicate_selected():
        item = pack_list.currentItem()
        if not item:
            return
        source = item.text()
        name, ok = QInputDialog.getText(
            dialog,
            "パック複製",
            f"'{source}' のコピー名（英数字と_-のみ）:",
        )
        if not ok or not name:
            return
        try:
            destination = duplicate_pack(source, name)
            refresh_pack_list(destination.name)
        except Exception as error:
            QMessageBox.critical(
                dialog,
                "複製エラー",
                str(error),
            )

    def delete_selected():
        item = pack_list.currentItem()
        if not item:
            return
        name = item.text()
        if name in registry:
            QMessageBox.warning(
                dialog,
                "エラー",
                "組み込みパックは削除できません。",
            )
            return
        if (
            QMessageBox.question(
                dialog,
                "削除確認",
                f"パック '{name}' を削除しますか？",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            delete_user_pack(name)
            refresh_pack_list()
        except Exception as error:
            QMessageBox.critical(
                dialog,
                "削除エラー",
                str(error),
            )

    new_btn.clicked.connect(create_pack)
    dup_btn.clicked.connect(duplicate_selected)
    del_btn.clicked.connect(delete_selected)

    refresh_pack_list()
    dialog.exec()
