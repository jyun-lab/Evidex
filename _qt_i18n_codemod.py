import ast
import hashlib
import json
import re
from pathlib import Path


ROOT = Path("evidex/qt_app")
JA_PATH = Path("evidex/locales/ja.json")
EN_PATH = Path("evidex/locales/en.json")
JP_RE = re.compile(r"[ぁ-んァ-ヶ一-龠々ー]")

IMPORT_TARGETS = {
    "main_window.py",
    "detail.py",
    "filtering.py",
    "table_view.py",
    "record_ops.py",
    "record_dialog.py",
    "widgets.py",
    "waveform.py",
    "steps_dialog.py",
    "series_dialog.py",
    "popout.py",
    "theming.py",
    "schema_editor_dialog.py",
    "schema_fields.py",
    "schema_display.py",
}

# Reuse established tkinter/schema-editor keys when the wording has the same role.
KEY_OVERRIDES = {
    "タイムライン": "pane.label.timeline",
    "この記録には工程が登録されていません。": "pane.msg.no_steps",
    "この記録にはシリーズが割り当てられていません。": "pane.msg.no_series",
    "Grade推移:": "series.label.grade_seq",
    "確認済み事実": "series.field.established_knowns",
    "所見": "series.field.my_assessment",
    "（変更なし）": "pane.msg.no_change",
    "初期条件: ": "pane.label.initial_condition",
    "プリセット名を入力:": "prefs.msg.preset_name",
    "ステータス": "nav.section.status",
    "raw_pathあり": "search.filter.has_raw",
    "工程なし": "main.label.no_steps",
    "再読み込み": "menu.file.reload",
    "開く...": "menu.file.open",
    "アクティブなパック:": "dialog.settings.pack",
    "言語 / Language:": "dialog.settings.language",
    "raw_path あり": "main.label.has_raw",
    "粘度:": "main.label.viscosity",
    "日付:": "pane.field.date",
    "シリーズ:": "pane.field.series",
    "ステータス:": "main.label.status_colon",
    "液体:": "main.label.liquid_colon",
    "<  前へ": "btn.prev",
    "次へ  >": "btn.next",
    "CSVを選択...": "schema_editor.choose_csv",
    "列を再読込": "schema_editor.reload_columns",
    "X軸設定": "schema_editor.x_axis_settings",
    "X軸列:": "schema_editor.str16",
    "軸名:": "schema_editor.x_name",
    "単位:": "schema_editor.channel_unit",
    "チャンネル設定": "schema_editor.channel_settings",
    "全選択": "schema_editor.select_all",
    "全解除": "schema_editor.clear_selection",
    "設定を適用": "schema_editor.str27",
    "アダプター設定": "schema_editor.str4",
    "スキップ行数:": "schema_editor.str20",
    "区切り文字:": "schema_editor.str21",
    "X軸列以外の列がチャンネル候補になります。チェックした列を使用します。": "schema_editor.channel_help",
    "列名": "schema_editor.channel_column",
    "選択列の単位:": "schema_editor.channel_unit",
    "CSVファイルを選択": "schema_editor.choose_csv",
    "X軸列とチャンネル列を1つ以上選択してください。": "schema_editor.adapter_columns_required",
    "区切り文字は1文字にしてください。": "schema_editor.invalid_delimiter",
    "スキップ行数は0以上の整数を指定してください。": "schema_editor.invalid_skip",
    "ナビゲーション ファセット": "schema_editor.facets",
    "機能": "schema_editor.features",
    "Grade 色": "schema_editor.colors",
    "表示設定を適用": "schema_editor.apply_screen_settings",
    "表示設定": "schema_editor.str5",
    "ナビパネルに表示するフィールドを選択:": "schema_editor.facets_help",
    "工程管理": "schema_editor.feature_steps",
    "実験の各工程を記録・管理します": "schema_editor.feature_steps_help",
    "複数の実験をシリーズとしてグループ化します": "schema_editor.feature_series_help",
    "グレード評価": "schema_editor.feature_grading",
    "実験結果をA/B/Cでグレード付けします": "schema_editor.feature_grading_help",
    "ベースライン": "schema_editor.feature_baseline",
    "波形のベースライン補正を有効にします": "schema_editor.feature_baseline_help",
    "新規作成": "schema_editor.str44",
    "編集中:": "schema_editor.pack_to_edit",
    "テキスト": "schema_editor.type_text",
    "数値": "schema_editor.type_number",
    "フィールド編集": "schema_editor.str10",
    "カンマ区切り": "schema_editor.choices",
    "フィールドID:": "schema_editor.field_id",
    "日本語名:": "schema_editor.str11",
    "英語名:": "schema_editor.str12",
    "入力方式:": "schema_editor.str13",
    "選択肢:": "schema_editor.str14",
    "フィールド": "schema_editor.str3",
    "日本語名": "schema_editor.str8",
    "英語名": "schema_editor.english",
    "入力方式": "schema_editor.str9",
    "フィールドIDが不正です。英数字と_-のみ使用可能。": "schema_editor.invalid_field_id",
    "同じIDのフィールドが既に存在します。": "schema_editor.duplicate_field",
    "run_id は削除できません。": "schema_editor.run_id_required",
    "新規パック": "schema_editor.str37",
    "パック名（英数字と_-のみ）:": "schema_editor.str38",
    "パック複製": "schema_editor.str33",
    "（アクティブ）": "schema_editor.active_pack_status",
    "組み込みパック（読み取り専用）": "schema_editor.str6",
    "組み込みパックは削除できません。": "schema_editor.str30",
    "削除確認": "schema_editor.delete_title",
    "保存完了": "schema_editor.success_title",
    "再起動後に反映されます。": "schema_editor.restart_to_apply",
    "上へ": "btn.up",
    "下へ": "btn.down",
    "編集する工程を選択してください。": "steps.msg.select_edit",
    "削除する工程を選択してください。": "steps.msg.select_delete",
    "詳細を開く": "main.menu.show_detail",
    "raw_path を開く": "main.menu.open_raw",
    "excel_path を開く": "main.menu.open_excel",
    "パスをコピー": "main.menu.copy_paths",
    "空欄は自動。刻みは正の数だけ有効です。": "wave.msg.axis_hint",
    "基準: 先頭サンプル": "wave.label.base_head",
}

# New static strings that do not already have a suitable catalog entry.
NEW_EN = {
    "CSV/グラフ": "CSV / Graph",
    "記録を選択": "Select a record",
    "IDなし": "No ID",
    "左の表から実験記録を選択してください。": "Select an experiment record from the table on the left.",
    "実験記録を選択すると、登録ファイルがここに表示されます。": "Registered files appear here after you select an experiment record.",
    "実験記録を選択すると、raw_path のCSVと簡易グラフがここに表示されます。": "The raw_path CSV and a quick graph appear here after you select an experiment record.",
    "このシリーズは series.csv に未登録です。シリーズ管理から登録できます。": "This series is not registered in series.csv. You can register it in Series Manager.",
    "この記録にはファイルが登録されていません。": "No files are registered for this record.",
    "ファイルが見つかりません": "File Not Found",
    "ファイルを開けません": "Cannot Open File",
    "開く": "Open",
    "存在します": "Available",
    "見つかりません": "Missing",
    "プリセット保存": "Save Preset",
    "フィルタ: ": "Filters: ",
    "Evidex Qt プレビュー": "Evidex Qt Preview",
    "Qt版プレビューを起動しました。": "Evidex Qt Preview started.",
    "Qt版の試作画面です。Tkinter版も引き続き使えます。": "This is the Qt preview. The Tkinter version remains available.",
    "新しい実験記録を追加": "Add New Experiment Record",
    "ナビゲーションの表示を切り替え": "Toggle navigation",
    "ID、日付、タイトル、要約、ファイルパスなどから検索": "Search by ID, date, title, summary, file path, and more",
    "プリセット": "Preset",
    "実験記録を編集": "Edit Experiment Record",
    "実験記録を削除": "Delete Experiment Record",
    "ファイル(&F)": "&File",
    "表示(&V)": "&View",
    "ナビゲーション": "Navigation",
    "CSVファイルを開く": "Open CSV File",
    "チップ:": "Chip:",
    "実験者:": "Experimenter:",
    "理解度:": "Understanding:",
    "操作:": "Action:",
    "シリーズ(&S)": "&Series",
    "実験記録の詳細": "Experiment Record Details",
    "ID なし": "No ID",
    "編集する実験記録を選択してください。": "Select an experiment record to edit.",
    "削除する実験記録を選択してください。": "Select an experiment record to delete.",
    "工程を編集する実験記録を選択してください。": "Select an experiment record whose steps you want to edit.",
    "run_id がない記録の工程は編集できません。": "Steps cannot be edited for a record without a run_id.",
    "シリーズ管理の変更を反映しました。": "Series Manager changes have been applied.",
    "削除エラー": "Delete Error",
    "使用": "Use",
    "テスト成功": "Test Successful",
    "読み込みエラー": "Read Error",
    "テスト失敗": "Test Failed",
    "設定変更": "Settings Changed",
    "作成エラー": "Create Error",
    "複製エラー": "Duplicate Error",
    "series_id ごとに実験記録をまとめ、研究の目的や主張を確認できます。": "Group experiment records by series_id to review research objectives and claims.",
    "シリーズを選択": "Select a series",
    "シリーズを削除": "Delete Series",
    "所属実験": "Linked Experiments",
    "シリーズIDを入力してください。": "Enter a Series ID.",
    "シリーズがまだありません。新規シリーズを作成するか、実験記録に series_id を設定してください。": "There are no series yet. Create one or set series_id on an experiment record.",
    "左の一覧からシリーズを選択してください。": "Select a series from the list on the left.",
    "シリーズ情報を表示できません。": "Series information could not be displayed.",
    "series.csvに未登録です。「シリーズ情報を編集」で作成できます。": "Not registered in series.csv. Use Edit Series Info to create it.",
    "タイトル": "Title",
    "この実験記録に紐づく工程を表で編集します。No は保存時に上から順番で自動採番されます。": "Edit the steps linked to this experiment record in the table. Step numbers are assigned from top to bottom when saved.",
    "工程を追加": "Add Step",
    "選択した工程を編集": "Edit Selected Step",
    "選択した工程を削除": "Delete Selected Step",
    "このパックには工程項目が定義されていません。工程を使うには、パック設定で工程項目を追加してください。": "This pack does not define any step fields. Add step fields in the pack settings to use steps.",
    "工程を削除": "Delete Step",
    "raw_path が空です。": "raw_path is empty.",
    "グラフ: matplotlib が未インストールです": "Graph: matplotlib is not installed",
    "CSVを選択すると、ここにmatplotlibグラフが表示されます。": "Select a CSV file to display a matplotlib graph here.",
    "raw_path にCSVが登録されていません。実験記録を編集してCSVを追加すると、ここに表とグラフが表示されます。": "No CSV is registered in raw_path. Edit the experiment record and add a CSV to display its table and graph here.",
    "CSVが選択されていません。": "No CSV is selected.",
    "高品質グラフ表示には matplotlib が必要です。": "matplotlib is required for high-quality graph display.",
    "高品質グラフ表示には matplotlib が必要です。\n次のコマンドで追加できます: python -m pip install matplotlib": "matplotlib is required for high-quality graph display.\nInstall it with: python -m pip install matplotlib",
    "グラフにできる数値データがありません。": "There is no numeric data to graph.",
    "グラフにできる数値データが足りません。": "There is not enough numeric data to graph.",
    "グラフをクリックすると、対応するCSV行番号をクリップボードへコピーします。": "Click the graph to copy the corresponding CSV row number to the clipboard.",
    "このCSVは現在のパックのグラフ設定では読み込めません。表プレビューで中身を確認できます。": "This CSV cannot be read with the current pack's graph settings. You can inspect it in the table preview.",
    "ファイルを追加": "Add Files",
    "選択した項目を削除": "Remove Selected Items",
    "選択したファイルを開く": "Open Selected File",
    "ファイル名": "File Name",
    "パス": "Path",
}

# Dynamic strings are replaced as complete templates so English word order is correct.
# (file, original line): (replacement expression, key, Japanese template, English template)
JOINED = {
    ("detail.py", 221): (
        't("pane.label.series_title", sid=sid)',
        None, None, None,
    ),
    ("detail.py", 227): (
        't("series.label.summary", n=len(runs), period=period)',
        None, None, None,
    ),
    ("detail.py", 442): (
        't("qt.detail.images_count", n=len(image_entries))',
        "qt.detail.images_count", "画像 ({n})", "Images ({n})",
    ),
    ("detail.py", 565): (
        't("pane.msg.file_not_found", path=entry.resolved_path)',
        None, None, None,
    ),
    ("detail.py", 573): (
        't("qt.common.file_open_failed", path=entry.resolved_path)',
        "qt.common.file_open_failed", "ファイルを開けませんでした。\n{path}", "Could not open the file.\n{path}",
    ),
    ("filtering.py", 215): (
        't("btn.adv_filter", n=suffix, arrow=arrow)',
        None, None, None,
    ),
    ("filtering.py", 251): (
        't("btn.adv_filter", n=suffix, arrow=arrow)',
        None, None, None,
    ),
    ("filtering.py", 223): (
        't("qt.filter.viscosity_range", lo=lo, hi=hi)',
        "qt.filter.viscosity_range", "粘度: {lo}〜{hi}", "Viscosity: {lo}–{hi}",
    ),
    ("filtering.py", 225): (
        't("qt.filter.date_range", start=f["dfrom"] or "...", end=f["dto"] or "...")',
        "qt.filter.date_range", "日付: {start} 〜 {end}", "Date: {start} – {end}",
    ),
    ("record_dialog.py", 32): (
        't("run.title.edit", run_id=row.get("run_id", ""))',
        None, None, None,
    ),
    ("record_ops.py", 53): (
        't("run.title.edit", run_id=self.current_row.get("run_id", ""))',
        None, None, None,
    ),
    ("record_ops.py", 82): (
        't("qt.run.saved", run_id=selected_run_id)',
        "qt.run.saved", "実験記録「{run_id}」を保存しました。", 'Saved experiment record "{run_id}".',
    ),
    ("record_ops.py", 125): (
        't("qt.run.added", run_id=selected_run_id)',
        "qt.run.added", "実験記録「{run_id}」を追加しました。", 'Added experiment record "{run_id}".',
    ),
    ("record_ops.py", 140): (
        't("qt.run.confirm_delete", run_id=run_id)',
        "qt.run.confirm_delete",
        "実験記録「{run_id}」を削除しますか？\n\nこの操作は runs.csv から記録を削除します。\n削除前のCSVは backup フォルダに保存されます。",
        'Delete experiment record "{run_id}"?\n\nThis removes the record from runs.csv.\nA copy of the CSV is saved in the backup folder first.',
    ),
    ("record_ops.py", 166): (
        't("qt.run.deleted", run_id=run_id)',
        "qt.run.deleted", "実験記録「{run_id}」を削除しました。", 'Deleted experiment record "{run_id}".',
    ),
    ("record_ops.py", 192): (
        't("qt.steps.saved", run_id=run_id)',
        "qt.steps.saved", "工程「{run_id}」を保存しました。", 'Saved steps for "{run_id}".',
    ),
    ("schema_adapter.py", 229): (
        't("qt.schema_adapter.csv_info", encoding=inspected["encoding"], columns=len(inspected["header"]))',
        "qt.schema_adapter.csv_info", "エンコーディング: {encoding}, 列数: {columns}", "Encoding: {encoding}, Columns: {columns}",
    ),
    ("schema_adapter.py", 371): (
        't("qt.schema_adapter.test_success", points=len(signal.x.values), channels=len(signal.channels))',
        "qt.schema_adapter.test_success", "読込成功: {points}ポイント, {channels}チャンネル", "Import succeeded: {points} points, {channels} channels",
    ),
    ("schema_display.py", 161): (
        't("schema_editor.invalid_color", grade=grade)',
        None, None, None,
    ),
    ("schema_packs.py", 290): (
        't("qt.schema_packs.copy_name_prompt", source=source)',
        "qt.schema_packs.copy_name_prompt", "「{source}」のコピー名（英数字と_-のみ）:", 'Name for a copy of "{source}" (letters, numbers, _ and - only):',
    ),
    ("schema_packs.py", 320): (
        't("schema_editor.delete_confirm", pack_name=name)',
        None, None, None,
    ),
    ("schema_packs.py", 234): (
        't("schema_editor.saved_use_pack", pack_name=name)',
        None, None, None,
    ),
    ("series_dialog.py", 316): (
        't("series.label.summary", n=row["n"], period=row["period"])',
        None, None, None,
    ),
    ("series_dialog.py", 346): (
        't("series.label.runs", n=len(runs))',
        None, None, None,
    ),
    ("series_dialog.py", 473): (
        't("series.msg.confirm_delete_with_runs", sid=series_id, n=len(runs))',
        None, None, None,
    ),
    ("series_dialog.py", 477): (
        't("series.msg.confirm_delete", sid=series_id)',
        None, None, None,
    ),
    ("series_dialog.py", 523): (
        't("series.title.edit", sid=row.get("series_id", ""))',
        None, None, None,
    ),
    ("series_dialog.py", 319): (
        't("qt.series.grade_sequence", grades=row["grades"])',
        "qt.series.grade_sequence", "Grade推移: {grades}", "Grades: {grades}",
    ),
    ("series_dialog.py", 424): (
        't("series.msg.duplicate", sid=series_id)',
        None, None, None,
    ),
    ("steps_dialog.py", 36): (
        't("steps.title.edit", run_id=run_id)',
        None, None, None,
    ),
    ("steps_dialog.py", 48): (
        't("steps.title.edit", run_id=run_id)',
        None, None, None,
    ),
    ("table_view.py", 117): (
        't("qt.table.status_count", path=self.record_table.records_csv, shown=shown, total=total)',
        "qt.table.status_count", "{path}  |  {shown} / {total} 件", "{path}  |  {shown} / {total} records",
    ),
    ("table_view.py", 113): (
        't("search.label.count", hits=shown, total=total)',
        None, None, None,
    ),
    ("table_view.py", 115): (
        't("qt.table.total_count", total=total)',
        "qt.table.total_count", "{total} 件", "{total} records",
    ),
    ("table_view.py", 187): (
        't("qt.table.no_file_for_column", column=column)',
        "qt.table.no_file_for_column", "{column} にファイルが登録されていません。", "No file is registered in {column}.",
    ),
    ("table_view.py", 212): (
        't("tree.msg.paths_copied", n=len(paths))',
        None, None, None,
    ),
    ("waveform.py", 312): (
        't("qt.waveform.preview_summary", file=path.name, total=preview.total_rows, shown=len(preview.rows), encoding=preview.encoding)',
        "qt.waveform.preview_summary",
        "{file}  |  {total} 行中 {shown} 行を表示  |  encoding={encoding}",
        "{file}  |  showing {shown} of {total} rows  |  encoding={encoding}",
    ),
    ("waveform.py", 657): (
        't("qt.waveform.row_copied", x=event.xdata, row=row_number)',
        "qt.waveform.row_copied", "x={x:.3g} -> CSV行 {row} をコピーしました。", "x={x:.3g} -> copied CSV row {row}.",
    ),
    ("waveform.py", 303): (
        't("wave.msg.not_found", path=path)',
        None, None, None,
    ),
    ("waveform.py", 317): (
        't("qt.waveform.preview_error", error=error)',
        "qt.waveform.preview_error", "CSV表プレビューを作れませんでした: {error}", "Could not create the CSV table preview: {error}",
    ),
    ("waveform.py", 330): (
        't("qt.waveform.graph_status", x_name=signal.x.name, channels=channels)',
        "qt.waveform.graph_status", "グラフ: {x_name} を横軸に {channels} を表示", "Graph: {channels} plotted against {x_name}",
    ),
    ("waveform.py", 335): (
        't("qt.waveform.graph_read_error", error=error)',
        "qt.waveform.graph_read_error", "グラフ: 読み込み不可 ({error})", "Graph: could not read data ({error})",
    ),
    ("waveform.py", 499): (
        't("wave.label.base_row", row=int(base_row))',
        None, None, None,
    ),
    ("widgets.py", 157): (
        't("pane.msg.file_not_found", path=resolved)',
        None, None, None,
    ),
    ("widgets.py", 166): (
        't("qt.common.file_open_failed", path=resolved)',
        None, None, None,
    ),
}

SPECIAL_SIMPLE = {
    ("main_window.py", 164): 't("btn.adv_filter", n="", arrow="▸")',
}


def docstring_nodes(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                result.add(id(node.body[0].value))
    return result


def char_position(lines, line_number, byte_column):
    line = lines[line_number - 1]
    char_column = len(line.encode("utf-8")[:byte_column].decode("utf-8"))
    return sum(len(item) for item in lines[: line_number - 1]) + char_column


def make_key(value, en, used_keys):
    words = re.findall(r"[a-z0-9]+", en.lower())
    slug = "_".join(words[:8]) or "text"
    slug = slug[:72].rstrip("_")
    key = f"qt.common.{slug}"
    if key in used_keys:
        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:6]
        key = f"{key}_{digest}"
    used_keys.add(key)
    return key


ja = json.loads(JA_PATH.read_text(encoding="utf-8"))
en = json.loads(EN_PATH.read_text(encoding="utf-8"))
value_to_keys = {}
for key, value in ja.items():
    value_to_keys.setdefault(value, []).append(key)
used_keys = set(ja) | set(en)
new_value_keys = {}


def key_for_value(value):
    if value in KEY_OVERRIDES:
        key = KEY_OVERRIDES[value]
        if key not in ja or key not in en:
            raise KeyError(f"Missing overridden locale key: {key}")
        return key
    keys = value_to_keys.get(value)
    if keys:
        return keys[0]
    if value not in NEW_EN:
        raise KeyError(f"No translation mapping for: {value!r}")
    if value not in new_value_keys:
        key = make_key(value, NEW_EN[value], used_keys)
        new_value_keys[value] = key
        ja[key] = value
        en[key] = NEW_EN[value]
    return new_value_keys[value]


for joined_info in JOINED.values():
    _replacement, key, ja_text, en_text = joined_info
    if key:
        ja[key] = ja_text
        en[key] = en_text

outputs = {}
for path in sorted(ROOT.glob("*.py")):
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source)
    docs = docstring_nodes(tree)
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    edits = []
    handled_joined = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and JP_RE.search(node.value)
            and id(node) not in docs
        ):
            continue
        parent = parents.get(id(node))
        if isinstance(parent, ast.JoinedStr):
            parent_id = id(parent)
            if parent_id in handled_joined:
                continue
            handled_joined.add(parent_id)
            joined_key = (path.name, parent.lineno)
            if joined_key not in JOINED:
                raise KeyError(f"No joined-string mapping for {joined_key}")
            replacement = JOINED[joined_key][0]
            start = char_position(lines, parent.lineno, parent.col_offset)
            end = char_position(lines, parent.end_lineno, parent.end_col_offset)
            edits.append((start, end, replacement))
            continue

        special = SPECIAL_SIMPLE.get((path.name, node.lineno))
        replacement = special or f't("{key_for_value(node.value)}")'
        start = char_position(lines, node.lineno, node.col_offset)
        end = char_position(lines, node.end_lineno, node.end_col_offset)
        edits.append((start, end, replacement))

    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]

    if path.name in IMPORT_TARGETS and "from evidex.core.i18n import t" not in source:
        updated_tree = ast.parse(source)
        imports = [
            node
            for node in updated_tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        if not imports:
            raise RuntimeError(f"No import block found in {path}")
        insert_line = imports[-1].end_lineno
        source_lines = source.splitlines(keepends=True)
        source_lines.insert(insert_line, "from evidex.core.i18n import t\n")
        source = "".join(source_lines)

    ast.parse(source)
    outputs[path] = source

for path, source in outputs.items():
    path.write_text(source, encoding="utf-8")
JA_PATH.write_text(
    json.dumps(ja, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
EN_PATH.write_text(
    json.dumps(en, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
