"""Display settings tab logic for the schema editor dialog."""

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class SchemaDisplayMixin:
    """表示設定タブの UI 構築とロジック。"""

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
