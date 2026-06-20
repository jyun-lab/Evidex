from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from evidex.core.attachments import split_paths
from evidex.core.csv_preview import load_csv_preview
from evidex.core.fields import WAVEFORM, feature_enabled
from evidex.core.filtering import fnum
from evidex.core.record_table import resolve_record_file_path
from evidex.core.steps_table import load_steps_table
from evidex.packs import active_pack

try:
    from matplotlib.figure import Figure
    from matplotlib.ticker import MultipleLocator
    try:
        from matplotlib.backends.backend_qtagg import (
            FigureCanvasQTAgg,
            NavigationToolbar2QT,
        )
    except Exception:
        from matplotlib.backends.backend_qt5agg import (
            FigureCanvasQTAgg,
            NavigationToolbar2QT,
        )
    MPL_AVAILABLE = True
except Exception:
    Figure = None
    FigureCanvasQTAgg = None
    NavigationToolbar2QT = None
    MultipleLocator = None
    MPL_AVAILABLE = False


def waveform_modes(config):
    modes = config.get("modes", [])
    if modes:
        return modes
    return [
        {
            "id": "all",
            "label": "Channels",
            "y_label": "Value",
            "channels": "all",
        }
    ]


def waveform_mode(config, mode_id):
    modes = waveform_modes(config)
    return next(
        (mode for mode in modes if mode.get("id") == mode_id),
        next(
            (
                mode for mode in modes
                if mode.get("id") == config.get("default_mode")
            ),
            modes[0],
        ),
    )


def waveform_channels(signal, mode):
    selected = mode.get("channels")
    if selected == "all":
        return [channel.name for channel in signal.channels]
    if isinstance(selected, list):
        return selected
    return signal.meta.get("groups", {}).get(mode.get("group", ""), [])


class RawDataPreviewWidget(QWidget):
    def __init__(self, row, records_csv, parent=None):
        super().__init__(parent)
        self.row = row
        self.records_csv = records_csv
        self.wave_config = WAVEFORM or {}
        self.modes = waveform_modes(self.wave_config)
        self.mode_id = self.wave_config.get("default_mode") or self.modes[0].get("id", "all")
        self.base_enabled = False
        self.axis_open = False
        self.axis_settings = {}
        self.axis_inputs = {}
        self.mode_buttons = {}
        self.current_signal = None
        self.current_path = None
        self.steps_by_run = {}
        if self.wave_config.get("step_markers", False) and feature_enabled("steps"):
            try:
                self.steps_by_run, _fields, _mtime = load_steps_table(records_csv)
            except Exception:
                self.steps_by_run = {}
        self.files = [
            resolve_record_file_path(path, records_csv)
            for path in split_paths(row.get("raw_path", ""))
        ]

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        if not self.files:
            message = QLabel(
                "raw_path にCSVが登録されていません。実験記録を編集してCSVを追加すると、ここに表とグラフが表示されます。"
            )
            message.setWordWrap(True)
            message.setStyleSheet("color: #667085;")
            root.addWidget(message)
            root.addStretch()
            return

        top = QHBoxLayout()
        top.addWidget(QLabel("CSV"))
        self.file_combo = QComboBox()
        for path in self.files:
            self.file_combo.addItem(path.name, str(path))
        self.file_combo.currentIndexChanged.connect(self.load_selected_file)
        self.open_button = QPushButton("開く")
        self.open_button.clicked.connect(self.open_selected_file)
        top.addWidget(self.file_combo, stretch=1)
        top.addWidget(self.open_button)
        root.addLayout(top)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #667085;")
        root.addWidget(self.status_label)

        self.controls_widget = QWidget()
        self.controls_layout = QVBoxLayout(self.controls_widget)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(6)
        self.build_wave_controls()
        root.addWidget(self.controls_widget)

        self.plot = SignalPlotWidget()
        root.addWidget(self.plot)

        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setShowGrid(True)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setMinimumHeight(170)
        self.preview_table.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #D0D7DE;
                alternate-background-color: #F6F8FA;
            }
            QHeaderView::section {
                background: #EEF2F6;
                border: 1px solid #D0D7DE;
                padding: 5px;
                font-weight: 600;
            }
            """
        )
        root.addWidget(self.preview_table, stretch=1)

        self.load_selected_file()

    def build_wave_controls(self):
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        if len(self.modes) > 1:
            top.addWidget(QLabel("表示"))
            for mode in self.modes:
                button = QPushButton(mode.get("label", mode.get("id", "all")))
                button.setCheckable(True)
                button.setChecked(mode.get("id", "all") == self.mode_id)
                button.clicked.connect(
                    lambda _checked=False, mode_id=mode.get("id", "all"): self.set_mode(mode_id)
                )
                self.mode_buttons[mode.get("id", "all")] = button
                top.addWidget(button)
        if feature_enabled("baseline"):
            self.base_button = QPushButton("基準補正")
            self.base_button.setCheckable(True)
            self.base_button.clicked.connect(self.toggle_base)
            top.addWidget(self.base_button)
        self.axis_button = QPushButton("軸設定 ▸")
        self.axis_button.clicked.connect(self.toggle_axis_panel)
        top.addWidget(self.axis_button)
        top.addStretch()
        self.controls_layout.addLayout(top)

        self.axis_panel = QWidget()
        axis_layout = QVBoxLayout(self.axis_panel)
        axis_layout.setContentsMargins(0, 0, 0, 0)
        axis_layout.setSpacing(4)
        for items in (
            [("xmin", "X最小"), ("xmax", "X最大"), ("xstep", "X刻み")],
            [("ymin", "Y最小"), ("ymax", "Y最大"), ("ystep", "Y刻み")],
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            for key, label in items:
                row.addWidget(QLabel(label))
                editor = QLineEdit()
                editor.setFixedWidth(72)
                self.axis_inputs[key] = editor
                row.addWidget(editor)
            row.addStretch()
            axis_layout.addLayout(row)
        buttons = QHBoxLayout()
        apply_button = QPushButton("適用")
        auto_button = QPushButton("自動")
        apply_button.clicked.connect(self.apply_axis_settings)
        auto_button.clicked.connect(self.clear_axis_settings)
        buttons.addWidget(apply_button)
        buttons.addWidget(auto_button)
        hint = QLabel("空欄は自動。刻みは正の数だけ有効です。")
        hint.setStyleSheet("color: #667085;")
        buttons.addWidget(hint)
        buttons.addStretch()
        axis_layout.addLayout(buttons)
        self.axis_panel.setVisible(False)
        self.controls_layout.addWidget(self.axis_panel)

    def selected_path(self):
        if not hasattr(self, "file_combo"):
            return None
        value = self.file_combo.currentData()
        return Path(value) if value else None

    def open_selected_file(self):
        path = self.selected_path()
        if path is None or not path.exists():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def set_mode(self, mode_id):
        self.mode_id = mode_id
        for key, button in self.mode_buttons.items():
            button.setChecked(key == mode_id)
        self.load_selected_file()

    def toggle_base(self):
        self.base_enabled = bool(self.base_button.isChecked())
        self.redraw_current_signal()

    def toggle_axis_panel(self):
        self.axis_open = not self.axis_open
        self.axis_panel.setVisible(self.axis_open)
        self.axis_button.setText("軸設定 ▾" if self.axis_open else "軸設定 ▸")

    def apply_axis_settings(self):
        self.axis_settings = {
            key: editor.text().strip()
            for key, editor in self.axis_inputs.items()
        }
        self.redraw_current_signal()

    def clear_axis_settings(self):
        self.axis_settings = {}
        for editor in self.axis_inputs.values():
            editor.clear()
        self.redraw_current_signal()

    def redraw_current_signal(self):
        if self.current_signal is None:
            return
        self.plot.set_signal(
            self.current_signal,
            mode_config=waveform_mode(self.wave_config, self.mode_id),
            base=self.base_enabled,
            row=self.row,
            steps=self.steps_by_run.get(self.row.get("run_id", ""), []),
            axis_settings=self.axis_settings,
        )

    def load_selected_file(self):
        path = self.selected_path()
        self.current_path = path
        self.current_signal = None
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)
        self.plot.set_signal(None)
        if path is None:
            self.status_label.setText("CSVが選択されていません。")
            self.open_button.setEnabled(False)
            return
        if not path.exists():
            self.status_label.setText(f"CSVが見つかりません: {path}")
            self.open_button.setEnabled(False)
            return
        self.open_button.setEnabled(True)

        try:
            preview = load_csv_preview(path)
            self.populate_csv_table(preview)
            table_message = (
                f"{path.name}  |  {preview.total_rows} 行中 "
                f"{len(preview.rows)} 行を表示  |  encoding={preview.encoding}"
            )
        except Exception as error:
            preview = None
            table_message = f"CSV表プレビューを作れませんでした: {error}"

        if not MPL_AVAILABLE:
            self.plot.set_message(
                "高品質グラフ表示には matplotlib が必要です。"
            )
            graph_message = "グラフ: matplotlib が未インストールです"
        else:
            try:
                signal = active_pack().parse(path)
                self.current_signal = signal
                self.redraw_current_signal()
                channels = ", ".join(channel.name for channel in signal.channels[:4])
                graph_message = f"グラフ: {signal.x.name} を横軸に {channels} を表示"
            except Exception as error:
                self.plot.set_message(
                    "このCSVは現在のパックのグラフ設定では読み込めません。表プレビューで中身を確認できます。"
                )
                graph_message = f"グラフ: 読み込み不可 ({error})"

        self.status_label.setText(f"{table_message}\n{graph_message}")

    def populate_csv_table(self, preview):
        self.preview_table.setColumnCount(len(preview.header))
        self.preview_table.setRowCount(len(preview.rows))
        self.preview_table.setHorizontalHeaderLabels(preview.header)
        for row_index, row in enumerate(preview.rows):
            for column_index, value in enumerate(row[: len(preview.header)]):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.preview_table.setItem(row_index, column_index, item)
        header = self.preview_table.horizontalHeader()
        for column_index in range(len(preview.header)):
            header.setSectionResizeMode(column_index, QHeaderView.ResizeMode.Interactive)
            self.preview_table.setColumnWidth(column_index, 120)


class SignalPlotWidget(QWidget):
    MAX_POINTS = 8000
    SPAN_COLORS = ["#378ADD", "#1D9E75", "#BA7517", "#9B6DD6", "#C2543A"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.click_spm = None
        self.click_offset = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if not MPL_AVAILABLE:
            self.message_label = QLabel(
                "高品質グラフ表示には matplotlib が必要です。\n"
                "次のコマンドで追加できます: python -m pip install matplotlib"
            )
            self.message_label.setWordWrap(True)
            self.message_label.setStyleSheet(
                "color: #667085; padding: 16px; border: 1px solid #D0D7DE; "
                "border-radius: 8px; background: #FFFFFF;"
            )
            layout.addWidget(self.message_label)
            return

        self.figure = Figure(figsize=(6.6, 3.0), dpi=110)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(self.canvas)
        layout.addWidget(self.toolbar)
        self.click_label = QLabel("")
        self.click_label.setStyleSheet("color: #667085; font-size: 11px;")
        layout.addWidget(self.click_label)
        self.canvas.mpl_connect("button_press_event", self.on_plot_clicked)
        self.set_message("CSVを選択すると、ここにmatplotlibグラフが表示されます。")

    def set_signal(
        self,
        signal,
        mode_config=None,
        base=False,
        row=None,
        steps=None,
        axis_settings=None,
    ):
        if not MPL_AVAILABLE:
            return
        if signal is None:
            self.set_message("CSVを選択すると、ここにmatplotlibグラフが表示されます。")
            return
        self.draw_signal(
            signal,
            mode_config=mode_config,
            base=base,
            row=row or {},
            steps=steps or [],
            axis_settings=axis_settings or {},
        )

    def set_message(self, message):
        if not MPL_AVAILABLE:
            if hasattr(self, "message_label"):
                self.message_label.setText(message)
            return
        self.click_spm = None
        self.click_offset = None
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.axis("off")
        axis.text(
            0.02,
            0.92,
            message,
            transform=axis.transAxes,
            va="top",
            ha="left",
            color="#667085",
            wrap=True,
        )
        if hasattr(self, "click_label"):
            self.click_label.setText("")
        self.canvas.draw_idle()

    def draw_signal(self, signal, mode_config=None, base=False, row=None,
                    steps=None, axis_settings=None):
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        mode_config = mode_config or {
            "id": "all",
            "label": "Channels",
            "y_label": "Value",
            "channels": "all",
        }
        row = row or {}
        steps = steps or []
        axis_settings = axis_settings or {}
        x_values = list(signal.x.values)
        channel_names = waveform_channels(signal, mode_config)
        all_channels = {
            channel.name: channel for channel in signal.channels
        }
        channels = [
            all_channels[name] for name in channel_names
            if name in all_channels and all_channels[name].values
        ]
        if not x_values or not channels:
            self.set_message("グラフにできる数値データがありません。")
            return

        min_len = min([len(x_values), *(len(channel.values) for channel in channels)])
        if min_len < 2:
            self.set_message("グラフにできる数値データが足りません。")
            return

        x_values = x_values[:min_len]
        spm = signal.meta.get("samples_per_min")
        offset = signal.meta.get("row_offset", 2)
        self.click_spm = spm
        self.click_offset = offset
        if spm is not None:
            self.click_label.setText(
                "グラフをクリックすると、対応するCSV行番号をクリップボードへコピーします。"
            )
        else:
            self.click_label.setText("")

        base_offsets = {channel.name: 0.0 for channel in channels}
        t_base = None
        if base and spm is not None:
            base_row = fnum(row.get("base_row", ""))
            t_base = (
                (base_row - offset) / spm
                if base_row is not None else x_values[0]
            )
            base_index = min(
                range(len(x_values)),
                key=lambda index: abs(x_values[index] - t_base),
            )
            for channel in channels:
                base_offsets[channel.name] = channel.values[base_index]
            if base_row is not None:
                axis.set_title(
                    f"基準: 行{int(base_row)}",
                    fontsize=8,
                    loc="left",
                    color="#667085",
                )
            else:
                axis.set_title(
                    "基準: 先頭サンプル",
                    fontsize=8,
                    loc="left",
                    color="#667085",
                )

        step = max(1, min_len // self.MAX_POINTS)
        x_sample = x_values[:min_len:step]
        for channel in channels:
            y_values = [
                value - base_offsets[channel.name]
                for value in channel.values[:min_len]
            ]
            y_sample = y_values[::step]
            label = channel.name
            if channel.unit:
                label += f" [{channel.unit}]"
            if base:
                label += "-base"
            axis.plot(
                x_sample,
                y_sample,
                linewidth=1.4,
                marker=".",
                markersize=2.5,
                label=label,
            )

        x_unit = f" [{signal.x.unit}]" if signal.x.unit else ""
        axis.set_xlabel(f"{signal.x.name.capitalize()}{x_unit}")
        y_label = mode_config.get("y_label", "Value")
        selected_units = {channel.unit for channel in channels if channel.unit}
        if (
            mode_config.get("channels") == "all"
            and y_label == "Value"
            and len(selected_units) == 1
        ):
            y_label = f"Value [{next(iter(selected_units))}]"
        axis.set_ylabel(y_label)
        axis.grid(True, alpha=0.35)

        self.apply_axis_settings(axis, axis_settings)
        if t_base is not None:
            axis.axvline(t_base, color="#777", lw=0.9, ls=":")
        self.draw_step_markers(axis, steps, spm, offset)

        axis.legend(
            fontsize=8,
            loc="lower right",
            bbox_to_anchor=(1.0, 1.0),
            ncol=2,
            frameon=False,
            borderaxespad=0,
        )
        if step > 1:
            axis.set_title(
                f"{min_len:,} points shown with downsampling every {step} points",
                fontsize=9,
                color="#667085",
                loc="right",
            )
        self.figure.tight_layout()
        self.figure.subplots_adjust(top=0.86)
        self.canvas.draw_idle()

    def apply_axis_settings(self, axis, settings):
        def axis_value(key):
            return fnum(settings.get(key, ""))

        if axis_value("xmin") is not None or axis_value("xmax") is not None:
            axis.set_xlim(left=axis_value("xmin"), right=axis_value("xmax"))
        if axis_value("ymin") is not None or axis_value("ymax") is not None:
            axis.set_ylim(bottom=axis_value("ymin"), top=axis_value("ymax"))
        x_step = axis_value("xstep")
        y_step = axis_value("ystep")
        if x_step is not None and x_step > 0:
            axis.xaxis.set_major_locator(MultipleLocator(x_step))
        if y_step is not None and y_step > 0:
            axis.yaxis.set_major_locator(MultipleLocator(y_step))

    def draw_step_markers(self, axis, steps, spm, offset):
        if not steps:
            return
        has_rows = any(
            fnum(step.get("data_start_row", "")) is not None
            for step in steps
        )
        if has_rows and spm is not None:
            for index, step in enumerate(steps):
                start_row = fnum(step.get("data_start_row", ""))
                if start_row is None:
                    continue
                end_row = fnum(step.get("data_end_row", ""))
                start_x = (start_row - offset) / spm
                label = (
                    f"{step.get('step_no', '')} {step.get('action', '')} "
                    f"{step.get('liquid', '')}"
                ).strip()
                color = self.SPAN_COLORS[index % len(self.SPAN_COLORS)]
                if end_row is not None:
                    end_x = (end_row - offset) / spm
                    axis.axvspan(start_x, end_x, color=color, alpha=0.10)
                axis.axvline(start_x, ls="--", lw=0.9, color=color, alpha=0.9)
                axis.text(
                    start_x,
                    axis.get_ylim()[1],
                    label,
                    fontsize=7,
                    rotation=90,
                    va="top",
                    ha="right",
                    color=color,
                )
            return

        total = 0.0
        for step in steps:
            duration = fnum(step.get("duration_min", ""))
            label = (
                f"{step.get('step_no', '')} {step.get('action', '')} "
                f"{step.get('liquid', '')}"
            ).strip()
            axis.axvline(total, ls="--", lw=0.9, color="#BA7517", alpha=0.8)
            axis.text(
                total,
                axis.get_ylim()[1],
                label,
                fontsize=7,
                rotation=90,
                va="top",
                ha="right",
                color="#854F0B",
            )
            if duration is None:
                break
            total += duration

    def on_plot_clicked(self, event):
        if self.click_spm is None or self.click_offset is None:
            return
        if event.xdata is None or getattr(event, "button", 1) != 1:
            return
        toolbar_mode = getattr(self.toolbar, "mode", "")
        if toolbar_mode:
            return
        row_number = max(
            int(self.click_offset),
            int(round(event.xdata * self.click_spm)) + int(self.click_offset),
        )
        QApplication.clipboard().setText(str(row_number))
        self.click_label.setText(
            f"x={event.xdata:.3g} -> CSV行 {row_number} をコピーしました。"
        )
