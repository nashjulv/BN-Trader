"""自动化投资任务台。"""

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import Config
from gui.styles import Theme
from services.automation_manager import (
    AutomationManager,
    AutomationTask,
    EVALUATING,
    ERROR,
    RUNNING,
)


STRATEGY_LABELS = {
    "AUTO": "场景自动匹配",
    "TRENDING": "趋势策略",
    "RANGING": "震荡策略",
    "BREAKOUT": "突破策略",
    "REVERSAL": "反转策略",
    "EXTREME": "极端策略",
}
DIRECTION_LABELS = {"BOTH": "双向", "LONG": "仅做多", "SHORT": "仅做空"}
STATUS_LABELS = {
    "STOPPED": "已停止",
    RUNNING: "运行中",
    EVALUATING: "评估中",
    ERROR: "异常停止",
}


class AutomationTaskDialog(QDialog):
    def __init__(
        self, symbols: list[str], task: AutomationTask = None, parent=None
    ):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("编辑自动化任务" if task else "新增自动化任务")
        self.setMinimumWidth(440)
        form = QFormLayout(self)
        form.setContentsMargins(24, 22, 24, 20)
        form.setSpacing(12)

        self.name = QLineEdit()
        self.symbol = QComboBox()
        self.symbol.addItems(symbols)
        self.timeframe = QComboBox()
        self.timeframe.addItems(["1m", "5m", "15m", "30m", "1h", "4h", "1d"])
        self.strategy = QComboBox()
        for key, label in STRATEGY_LABELS.items():
            self.strategy.addItem(label, key)
        self.direction = QComboBox()
        for key, label in DIRECTION_LABELS.items():
            self.direction.addItem(label, key)

        self.per_trade = QDoubleSpinBox()
        self.per_trade.setRange(1, 100)
        self.per_trade.setSuffix(" %")
        self.per_trade.setDecimals(1)
        self.interval = QSpinBox()
        self.interval.setRange(15, 86400)
        self.interval.setSuffix(" 秒")
        self.daily_limit = QSpinBox()
        self.daily_limit.setRange(1, 100)
        self.daily_limit.setSuffix(" 次")

        for label, widget in [
            ("任务名称", self.name),
            ("交易对", self.symbol),
            ("K 线周期", self.timeframe),
            ("执行策略", self.strategy),
            ("允许方向", self.direction),
            ("单次使用币种预算", self.per_trade),
            ("策略评估周期", self.interval),
            ("每日最大执行", self.daily_limit),
        ]:
            form.addRow(label, widget)

        hint = QLabel(
            "任务保存后不会自动运行；必须在任务台手动启动。"
            "固定策略只在行情场景与该策略匹配时执行。"
        )
        hint.setObjectName("captionLabel")
        hint.setWordWrap(True)
        form.addRow("", hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        if task:
            self.name.setText(task.name)
            self.symbol.setCurrentText(task.symbol)
            self.timeframe.setCurrentText(task.timeframe)
            self.strategy.setCurrentIndex(
                self.strategy.findData(task.strategy)
            )
            self.direction.setCurrentIndex(
                self.direction.findData(task.direction)
            )
            self.per_trade.setValue(task.per_trade_ratio * 100)
            self.interval.setValue(task.interval_seconds)
            self.daily_limit.setValue(task.max_trades_per_day)
        else:
            self.name.setText("新自动化任务")
            self.timeframe.setCurrentText("15m")
            self.per_trade.setValue(20)
            self.interval.setValue(60)
            self.daily_limit.setValue(5)

    def _accept(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "无法保存", "请输入任务名称。")
            self.name.setFocus()
            return
        self.accept()

    def values(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "symbol": self.symbol.currentText(),
            "timeframe": self.timeframe.currentText(),
            "strategy": self.strategy.currentData(),
            "direction": self.direction.currentData(),
            "per_trade_ratio": self.per_trade.value() / 100,
            "interval_seconds": self.interval.value(),
            "max_trades_per_day": self.daily_limit.value(),
        }


class AllocationDialog(QDialog):
    """新增或编辑一个参与自动化投资的交易对。"""

    def __init__(
        self,
        existing_symbols: list[str],
        symbol: str = "",
        ratio: float = 0.10,
        enabled: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._editing = bool(symbol)
        self.setWindowTitle("编辑资金分配" if symbol else "新增投资币种")
        self.setMinimumWidth(420)
        form = QFormLayout(self)
        form.setContentsMargins(24, 22, 24, 20)
        form.setSpacing(12)

        self.symbol = QComboBox()
        self.symbol.setEditable(True)
        choices = list(dict.fromkeys(Config.DEFAULT_SYMBOLS + existing_symbols))
        self.symbol.addItems(choices)
        self.symbol.setCurrentText(symbol or next(
            (item for item in choices if item not in existing_symbols), "ADAUSDT"
        ))
        self.symbol.setEnabled(not self._editing)

        self.ratio = QDoubleSpinBox()
        self.ratio.setRange(0.1, 100)
        self.ratio.setDecimals(1)
        self.ratio.setSuffix(" %")
        self.ratio.setValue(ratio * 100)
        self.enabled = QCheckBox("参与自动化投资")
        self.enabled.setChecked(enabled)

        form.addRow("交易对", self.symbol)
        form.addRow("总资金分配", self.ratio)
        form.addRow("投资状态", self.enabled)
        hint = QLabel(
            "可从列表选择，也可输入币安现货 USDT 交易对，例如 ADAUSDT。"
            "启用项目的总分配不能超过 100%。"
        )
        hint.setObjectName("captionLabel")
        hint.setWordWrap(True)
        form.addRow("", hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        return {
            "symbol": self.symbol.currentText(),
            "allocation_ratio": self.ratio.value() / 100,
            "enabled": self.enabled.isChecked(),
        }


class AutomationPage(QWidget):
    start_requested = pyqtSignal(str)
    stop_requested = pyqtSignal(str)
    start_all_requested = pyqtSignal()
    stop_all_requested = pyqtSignal()

    def __init__(self, manager: AutomationManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._total_capital = 0.0
        self._build_ui()
        self.refresh()
        self._refresh_theme()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title_row = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("自动化投资任务台")
        title.setObjectName("automationTitle")
        subtitle = QLabel(
            "按币种分配预算、选择策略并手动启动；所有订单继续受全局风控约束"
        )
        subtitle.setObjectName("captionLabel")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        title_row.addLayout(titles)
        title_row.addStretch()

        add_btn = QPushButton("新增任务")
        add_btn.setObjectName("ghostBtn")
        add_btn.setMinimumHeight(36)
        add_btn.clicked.connect(self._add_task)
        title_row.addWidget(add_btn)
        root.addLayout(title_row)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        self.running_value = QLabel("0")
        self.allocation_value = QLabel("0%")
        self.budget_value = QLabel("0 USDT")
        self.risk_value = QLabel("全局风控生效")
        for caption, value in [
            ("运行任务", self.running_value),
            ("已分配比例", self.allocation_value),
            ("自动化预算", self.budget_value),
            ("安全状态", self.risk_value),
        ]:
            metrics.addWidget(self._metric_card(caption, value), 1)
        root.addLayout(metrics)

        allocation_card = QFrame()
        allocation_card.setObjectName("automationCard")
        allocation_layout = QVBoxLayout(allocation_card)
        allocation_layout.setContentsMargins(14, 12, 14, 12)
        allocation_layout.setSpacing(8)
        allocation_header = QHBoxLayout()
        allocation_header.addWidget(self._section("币种资金分配"))
        self.remaining_label = QLabel("未分配 25%")
        self.remaining_label.setObjectName("captionLabel")
        allocation_header.addWidget(self.remaining_label)
        allocation_header.addStretch()
        add_allocation = QPushButton("新增币种")
        add_allocation.setObjectName("ghostBtn")
        add_allocation.clicked.connect(self._add_allocation)
        edit_allocation = QPushButton("编辑分配")
        edit_allocation.setObjectName("ghostBtn")
        edit_allocation.clicked.connect(self._edit_allocation)
        delete_allocation = QPushButton("删除币种")
        delete_allocation.setObjectName("dangerBtn")
        delete_allocation.clicked.connect(self._delete_allocation)
        allocation_header.addWidget(add_allocation)
        allocation_header.addWidget(edit_allocation)
        allocation_header.addWidget(delete_allocation)
        allocation_layout.addLayout(allocation_header)

        self.allocation_table = QTableWidget(0, 5)
        self.allocation_table.setHorizontalHeaderLabels([
            "交易对", "分配比例", "预算金额", "投资状态", "关联任务",
        ])
        self._configure_table(self.allocation_table, stretch_column=4)
        self.allocation_table.setMaximumHeight(178)
        self.allocation_table.verticalHeader().setDefaultSectionSize(38)
        self.allocation_table.doubleClicked.connect(self._edit_allocation)
        allocation_layout.addWidget(self.allocation_table)
        root.addWidget(allocation_card)

        table_card = QFrame()
        table_card.setObjectName("automationCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 12)
        table_layout.setSpacing(10)

        table_header = QHBoxLayout()
        table_header.addWidget(self._section("任务与资金调度"))
        table_header.addStretch()
        edit_btn = QPushButton("编辑")
        edit_btn.setObjectName("ghostBtn")
        edit_btn.clicked.connect(self._edit_selected)
        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("dangerBtn")
        delete_btn.clicked.connect(self._delete_selected)
        table_header.addWidget(edit_btn)
        table_header.addWidget(delete_btn)
        table_layout.addLayout(table_header)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "任务", "交易对", "策略", "币种预算", "单次", "周期",
            "今日", "状态", "上次评估", "执行说明",
        ])
        self._configure_table(self.table, stretch_column=9)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setMinimumHeight(164)
        self.table.doubleClicked.connect(self._edit_selected)
        table_layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.start_btn = QPushButton("启动选中任务")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setMinimumHeight(38)
        self.start_btn.clicked.connect(self._start_selected)
        stop_btn = QPushButton("停止选中")
        stop_btn.setObjectName("ghostBtn")
        stop_btn.clicked.connect(self._stop_selected)
        start_all = QPushButton("启动全部")
        start_all.setObjectName("ghostBtn")
        start_all.clicked.connect(self.start_all_requested.emit)
        stop_all = QPushButton("停止全部")
        stop_all.setObjectName("ghostBtn")
        stop_all.clicked.connect(self.stop_all_requested.emit)
        actions.addWidget(self.start_btn)
        actions.addWidget(stop_btn)
        actions.addSpacing(12)
        actions.addWidget(start_all)
        actions.addWidget(stop_all)
        actions.addStretch()
        safety = QLabel("启动前请确认策略、资金与 API 环境")
        safety.setObjectName("captionLabel")
        actions.addWidget(safety)
        table_layout.addLayout(actions)
        root.addWidget(table_card, 1)

        log_card = QFrame()
        log_card.setObjectName("automationCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(14, 12, 14, 12)
        log_layout.addWidget(self._section("任务执行记录"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(84)
        self.log.setPlaceholderText("启动任务后，这里会显示调度、策略和风控结果。")
        self.log.setAccessibleName("自动化任务执行记录")
        log_layout.addWidget(self.log)
        root.addWidget(log_card)

    @staticmethod
    def _configure_table(table: QTableWidget, stretch_column: int):
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        for column in range(table.columnCount()):
            mode = (
                QHeaderView.ResizeMode.Stretch
                if column == stretch_column
                else QHeaderView.ResizeMode.ResizeToContents
            )
            header.setSectionResizeMode(column, mode)

    def _metric_card(self, caption: str, value: QLabel) -> QFrame:
        card = QFrame()
        card.setObjectName("automationMetric")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 11, 14, 11)
        cap = QLabel(caption)
        cap.setObjectName("dimLabel")
        value.setObjectName("automationMetricValue")
        layout.addWidget(cap)
        layout.addWidget(value)
        return card

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def selected_task_id(self) -> str:
        row = self.table.currentRow()
        if row < 0:
            return ""
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def selected_allocation_symbol(self) -> str:
        row = self.allocation_table.currentRow()
        if row < 0:
            return ""
        item = self.allocation_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def refresh(self):
        selected_allocation = self.selected_allocation_symbol()
        self.allocation_table.setRowCount(len(self.manager.allocations))
        for row, allocation in enumerate(self.manager.allocations):
            related = sum(
                task.symbol == allocation.symbol for task in self.manager.tasks
            )
            values = [
                allocation.symbol.replace("USDT", "/USDT"),
                f"{allocation.allocation_ratio:.1%}",
                f"{self._total_capital * allocation.allocation_ratio:,.0f} USDT",
                "参与投资" if allocation.enabled else "已停用",
                f"{related} 个任务",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole, allocation.symbol
                    )
                if column in (1, 2, 3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.allocation_table.setItem(row, column, item)
            if selected_allocation == allocation.symbol:
                self.allocation_table.selectRow(row)
        if (
            self.allocation_table.rowCount()
            and self.allocation_table.currentRow() < 0
        ):
            self.allocation_table.selectRow(0)

        selected = self.selected_task_id()
        self.table.setRowCount(len(self.manager.tasks))
        for row, task in enumerate(self.manager.tasks):
            allocation = self.manager.allocation_for(
                task.symbol, enabled_only=False
            )
            values = [
                task.name,
                task.symbol.replace("USDT", "/USDT"),
                STRATEGY_LABELS.get(task.strategy, task.strategy),
                f"{allocation.allocation_ratio:.0%}" if allocation else "—",
                f"{task.per_trade_ratio:.0%}",
                f"{task.interval_seconds}s",
                f"{task.executions_today}/{task.max_trades_per_day}",
                STATUS_LABELS.get(task.status, task.status),
                task.last_run or "—",
                task.last_message,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, task.id)
                if column in (3, 4, 5, 6, 7, 8):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
            if selected == task.id:
                self.table.selectRow(row)
        if self.table.rowCount() and self.table.currentRow() < 0:
            self.table.selectRow(0)
        self.running_value.setText(str(self.manager.running_count()))
        ratio = self.manager.total_allocation()
        self.allocation_value.setText(f"{ratio:.0%}")
        self.budget_value.setText(f"{self._total_capital * ratio:,.0f} USDT")
        self.remaining_label.setText(f"未分配 {max(0, 1 - ratio):.1%}")
        self._apply_status_colors()

    def set_capital(self, total: float):
        self._total_capital = total
        self.refresh()

    def set_risk_state(self, allowed: bool, message: str):
        self.risk_value.setText("允许执行" if allowed else f"已拦截 · {message}")
        self.risk_value.setProperty("riskAllowed", allowed)
        self._refresh_theme()

    def add_log(self, message: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText(f"{stamp}  {message}")

    def _add_allocation(self):
        dialog = AllocationDialog(
            self.manager.investment_symbols(enabled_only=False), parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.manager.add_allocation(**values)
            self.refresh()
            self.add_log(
                f"已新增投资币种：{self.manager.normalize_symbol(values['symbol'])}"
            )
        except ValueError as error:
            QMessageBox.warning(self, "无法新增币种", str(error))

    def _edit_allocation(self):
        symbol = self.selected_allocation_symbol()
        allocation = self.manager.allocation_for(
            symbol, enabled_only=False
        )
        if not allocation:
            return
        dialog = AllocationDialog(
            self.manager.investment_symbols(enabled_only=False),
            allocation.symbol,
            allocation.allocation_ratio,
            allocation.enabled,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            values = dialog.values()
            self.manager.update_allocation(
                allocation.symbol,
                values["allocation_ratio"],
                enabled=values["enabled"],
            )
            self.refresh()
            state = "启用" if values["enabled"] else "停用"
            self.add_log(
                f"已更新资金分配：{allocation.symbol} · "
                f"{values['allocation_ratio']:.1%} · {state}"
            )
        except ValueError as error:
            QMessageBox.warning(self, "无法保存分配", str(error))

    def _delete_allocation(self):
        symbol = self.selected_allocation_symbol()
        allocation = self.manager.allocation_for(
            symbol, enabled_only=False
        )
        if not allocation:
            return
        related = sum(task.symbol == symbol for task in self.manager.tasks)
        detail = (
            f"确定删除 {symbol.replace('USDT', '/USDT')} 的资金分配吗？"
            f"\n同时会删除其关联的 {related} 个自动化任务。"
        )
        reply = QMessageBox.question(self, "删除投资币种", detail)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.manager.remove_allocation(symbol)
            self.refresh()
            self.add_log(f"已删除投资币种及关联任务：{symbol}")
        except ValueError as error:
            QMessageBox.warning(self, "无法删除币种", str(error))

    def _add_task(self):
        symbols = self.manager.investment_symbols()
        if not symbols:
            QMessageBox.information(
                self, "请先分配资金",
                "至少新增并启用一个投资币种后，才能创建自动化任务。"
            )
            return
        dialog = AutomationTaskDialog(symbols, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.manager.add(AutomationTask.create(**values))
            self.refresh()
            self.add_log(f"已新增任务：{values['name']}")
        except ValueError as error:
            QMessageBox.warning(self, "无法新增任务", str(error))

    def _edit_selected(self):
        task = self.manager.get(self.selected_task_id())
        if not task:
            return
        if task.status in (RUNNING, EVALUATING):
            QMessageBox.information(self, "请先停止", "运行中的任务不能编辑。")
            return
        dialog = AutomationTaskDialog(
            self.manager.investment_symbols(enabled_only=False), task, self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.manager.update(task.id, **dialog.values())
            self.refresh()
            self.add_log(f"已更新任务：{task.name}")
        except ValueError as error:
            QMessageBox.warning(self, "无法保存任务", str(error))

    def _delete_selected(self):
        task = self.manager.get(self.selected_task_id())
        if not task:
            return
        reply = QMessageBox.question(
            self, "删除任务", f"确定删除“{task.name}”吗？"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.manager.remove(task.id)
            self.refresh()
            self.add_log(f"已删除任务：{task.name}")
        except ValueError as error:
            QMessageBox.warning(self, "无法删除任务", str(error))

    def _start_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.start_requested.emit(task_id)

    def _stop_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.stop_requested.emit(task_id)

    def _apply_status_colors(self):
        t = Theme.colors()
        for row, allocation in enumerate(self.manager.allocations):
            status_item = self.allocation_table.item(row, 3)
            if status_item:
                status_item.setForeground(QColor(
                    t["success"] if allocation.enabled
                    else t["text_secondary"]
                ))
        for row, task in enumerate(self.manager.tasks):
            item = self.table.item(row, 7)
            if not item:
                continue
            color = (
                t["success"] if task.status == RUNNING
                else t["accent"] if task.status == EVALUATING
                else t["danger"] if task.status == ERROR
                else t["text_secondary"]
            )
            item.setForeground(QColor(color))

    def _refresh_theme(self):
        t = Theme.colors()
        allowed = self.risk_value.property("riskAllowed")
        risk_color = t["success"] if allowed is not False else t["danger"]
        self.setStyleSheet(f"""
            QWidget {{ background:{t['bg_main']}; }}
            QLabel#automationTitle {{
                color:{t['text_primary']}; background:transparent;
                font-size:24px; font-weight:650;
            }}
            QLabel#captionLabel, QLabel#dimLabel {{
                color:{t['text_secondary']}; background:transparent;
            }}
            QFrame#automationMetric, QFrame#automationCard {{
                background:{t['bg_card']}; border:1px solid {t['border']};
                border-radius:10px;
            }}
            QLabel#automationMetricValue {{
                color:{t['text_primary']}; background:transparent;
                font-size:18px; font-weight:650;
            }}
            QTableWidget {{
                background:{t['bg_card']}; color:{t['text_primary']};
                border:1px solid {t['divider']}; border-radius:8px;
                gridline-color:{t['divider']}; outline:none;
            }}
            QTableWidget::item:selected {{
                background:{t['accent_light']}; color:{t['text_primary']};
            }}
            QTableWidget::item:hover {{ background:{t['bg_hover']}; }}
            QHeaderView::section {{
                background:{t['bg_surface']}; color:{t['text_secondary']};
                border:none; border-bottom:1px solid {t['divider']};
                padding:8px; font-weight:600;
            }}
            QPlainTextEdit {{
                background:{t['bg_input']}; color:{t['text_secondary']};
                border:1px solid {t['border']}; border-radius:8px;
                padding:8px; font-family:'SF Mono','Consolas',monospace;
            }}
        """)
        self.risk_value.setStyleSheet(
            f"color:{risk_color}; background:transparent; "
            "font-size:14px; font-weight:600;"
        )
        self._apply_status_colors()
