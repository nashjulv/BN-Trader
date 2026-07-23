"""自动化投资任务模型、调度状态与持久化。"""

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4
import re

from config import Config
from utils.settings_store import load_json_settings, save_json_settings


TASKS_PATH = Config.PREFERENCES_DIR / "automation_tasks.json"

STOPPED = "STOPPED"
RUNNING = "RUNNING"
EVALUATING = "EVALUATING"
ERROR = "ERROR"


@dataclass
class AutomationTask:
    id: str
    name: str
    symbol: str
    timeframe: str = "15m"
    strategy: str = "AUTO"
    direction: str = "BOTH"
    per_trade_ratio: float = 0.25
    interval_seconds: int = 60
    max_trades_per_day: int = 5
    status: str = STOPPED
    last_run: str = ""
    next_run_ts: float = 0.0
    executions_today: int = 0
    last_message: str = "等待手动启动"

    @classmethod
    def create(cls, name: str, symbol: str, **kwargs):
        return cls(id=uuid4().hex[:12], name=name, symbol=symbol, **kwargs)

    @classmethod
    def from_dict(cls, value: dict):
        allowed = cls.__dataclass_fields__.keys()
        task = cls(**{key: val for key, val in value.items() if key in allowed})
        # 产品重启后不自动恢复执行，必须由客户再次确认。
        task.status = STOPPED
        task.next_run_ts = 0.0
        task.last_message = "等待手动启动"
        return task

    def persisted(self) -> dict:
        value = asdict(self)
        for key in ("status", "last_run", "next_run_ts",
                    "executions_today", "last_message"):
            value.pop(key, None)
        return value


@dataclass
class InvestmentAllocation:
    """一个参与自动化投资的交易对及其总资金预算。"""

    symbol: str
    allocation_ratio: float
    enabled: bool = True

    @classmethod
    def from_dict(cls, value: dict):
        return cls(
            symbol=str(value.get("symbol", "")).upper().replace("/", "").strip(),
            allocation_ratio=float(value.get("allocation_ratio", 0)),
            enabled=bool(value.get("enabled", True)),
        )


def default_allocations() -> list[InvestmentAllocation]:
    return [
        InvestmentAllocation("BTCUSDT", 0.35),
        InvestmentAllocation("ETHUSDT", 0.30),
        InvestmentAllocation("USDCUSDT", 0.10),
    ]


def default_tasks() -> list[AutomationTask]:
    return [
        AutomationTask.create(
            "BTC 趋势与场景任务", "BTCUSDT",
            per_trade_ratio=0.20,
        ),
        AutomationTask.create(
            "ETH 场景跟随任务", "ETHUSDT",
            per_trade_ratio=0.20,
        ),
        AutomationTask.create(
            "USDC 稳定币区间任务", "USDCUSDT",
            strategy="RANGING",
            per_trade_ratio=0.10, interval_seconds=120,
        ),
    ]


class AutomationManager:
    """管理任务配置和运行状态；交易执行由主窗口统一负责。"""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or TASKS_PATH
        defaults = {"tasks": [task.persisted() for task in default_tasks()]}
        raw = load_json_settings(self.path, defaults)
        allocation_items = raw.get("allocations")
        # 兼容第一版任务台：资金比例原来保存在每个任务中。
        if not isinstance(allocation_items, list):
            migrated = {}
            for item in raw.get("tasks", []):
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol", "")).upper()
                ratio = float(item.get("allocation_ratio", 0) or 0)
                if symbol and ratio > 0:
                    migrated[symbol] = migrated.get(symbol, 0) + ratio
            allocation_items = [
                {"symbol": symbol, "allocation_ratio": ratio, "enabled": True}
                for symbol, ratio in migrated.items()
            ] or [asdict(item) for item in default_allocations()]
        self.allocations = [
            InvestmentAllocation.from_dict(item)
            for item in allocation_items
            if isinstance(item, dict)
        ]
        self.tasks = [
            AutomationTask.from_dict(item)
            for item in raw.get("tasks", [])
            if isinstance(item, dict)
        ]
        if not self.tasks:
            self.tasks = default_tasks()
        if not self.allocations:
            self.allocations = default_allocations()
        self._busy_task_id: Optional[str] = None
        self.validate_allocations()

    def save(self):
        save_json_settings(
            self.path,
            {
                "tasks": [task.persisted() for task in self.tasks],
                "allocations": [asdict(item) for item in self.allocations],
            },
        )

    def get(self, task_id: str) -> Optional[AutomationTask]:
        return next((task for task in self.tasks if task.id == task_id), None)

    def add(self, task: AutomationTask):
        self._validate_task(task)
        if not self.allocation_for(task.symbol, enabled_only=False):
            raise ValueError("请先在资金分配表中添加该交易对")
        self.tasks.append(task)
        self.save()

    def update(self, task_id: str, **values):
        task = self.get(task_id)
        if not task:
            raise ValueError("任务不存在")
        candidate = AutomationTask.from_dict({**asdict(task), **values})
        candidate.status = task.status
        candidate.last_run = task.last_run
        candidate.next_run_ts = task.next_run_ts
        candidate.executions_today = task.executions_today
        candidate.last_message = task.last_message
        self._validate_task(candidate)
        if not self.allocation_for(candidate.symbol, enabled_only=False):
            raise ValueError("请先在资金分配表中添加该交易对")
        index = self.tasks.index(task)
        self.tasks[index] = candidate
        self.save()

    def remove(self, task_id: str):
        task = self.get(task_id)
        if task and task.status in (RUNNING, EVALUATING):
            raise ValueError("请先停止任务再删除")
        self.tasks = [item for item in self.tasks if item.id != task_id]
        self.save()

    def start(self, task_id: str, now_ts: Optional[float] = None):
        task = self.get(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status == EVALUATING:
            raise ValueError("任务正在评估，请等待本轮完成")
        self.validate_allocations()
        allocation = self.allocation_for(task.symbol)
        if not allocation:
            raise ValueError("该交易对未参与投资或已停用")
        if task.executions_today >= task.max_trades_per_day:
            raise ValueError("该任务已达到今日最大执行次数")
        task.status = RUNNING
        task.next_run_ts = now_ts or datetime.now().timestamp()
        task.last_message = "已启动，等待策略评估"

    def stop(self, task_id: str):
        task = self.get(task_id)
        if task:
            task.status = STOPPED
            task.next_run_ts = 0.0
            task.last_message = "已由客户手动停止"

    def stop_all(self):
        for task in self.tasks:
            self.stop(task.id)

    def due_task(self, now_ts: Optional[float] = None) -> Optional[AutomationTask]:
        if self._busy_task_id:
            return None
        now_ts = now_ts or datetime.now().timestamp()
        return next((
            task for task in self.tasks
            if task.status == RUNNING
            and task.executions_today < task.max_trades_per_day
            and task.next_run_ts <= now_ts
        ), None)

    def mark_evaluating(self, task_id: str):
        task = self.get(task_id)
        if not task:
            return
        self._busy_task_id = task_id
        task.status = EVALUATING
        task.last_message = "正在获取行情并评估策略"

    def finish_evaluation(
        self,
        task_id: str,
        message: str,
        *,
        success=True,
        now_ts: Optional[float] = None,
    ):
        task = self.get(task_id)
        if not task:
            return
        now_ts = now_ts or datetime.now().timestamp()
        if task.status == STOPPED:
            task.last_run = datetime.fromtimestamp(now_ts).strftime("%H:%M:%S")
            task.last_message = "本轮评估结果已忽略；任务已手动停止"
            self._busy_task_id = None
            return
        task.status = RUNNING if success else ERROR
        task.last_run = datetime.fromtimestamp(now_ts).strftime("%H:%M:%S")
        task.next_run_ts = now_ts + task.interval_seconds if success else 0.0
        task.last_message = message
        self._busy_task_id = None

    def record_execution(self, task_id: str, message: str):
        task = self.get(task_id)
        if not task:
            return
        task.executions_today += 1
        task.last_message = message
        if task.executions_today >= task.max_trades_per_day:
            task.status = STOPPED
            task.next_run_ts = 0.0
            task.last_message += "；已达到今日次数限制并停止"

    def allocation_for(
        self, symbol: str, *, enabled_only: bool = True
    ) -> Optional[InvestmentAllocation]:
        symbol = self.normalize_symbol(symbol)
        return next((
            item for item in self.allocations
            if item.symbol == symbol and (item.enabled or not enabled_only)
        ), None)

    def investment_symbols(self, *, enabled_only: bool = True) -> list[str]:
        return [
            item.symbol for item in self.allocations
            if item.enabled or not enabled_only
        ]

    def add_allocation(
        self, symbol: str, allocation_ratio: float, *, enabled: bool = True
    ):
        symbol = self.normalize_symbol(symbol)
        self._validate_allocation(
            InvestmentAllocation(symbol, allocation_ratio, enabled)
        )
        if self.allocation_for(symbol, enabled_only=False):
            raise ValueError("该交易对已在资金分配表中")
        if enabled and self.total_allocation() + allocation_ratio > 1.000001:
            raise ValueError("启用的资金分配合计不能超过 100%")
        self.allocations.append(
            InvestmentAllocation(symbol, allocation_ratio, enabled)
        )
        self.save()

    def update_allocation(
        self, symbol: str, allocation_ratio: float, *, enabled: bool
    ):
        allocation = self.allocation_for(symbol, enabled_only=False)
        if not allocation:
            raise ValueError("资金分配项不存在")
        candidate = InvestmentAllocation(
            allocation.symbol, allocation_ratio, enabled
        )
        self._validate_allocation(candidate)
        other_total = sum(
            item.allocation_ratio for item in self.allocations
            if item.symbol != allocation.symbol and item.enabled
        )
        if enabled and other_total + allocation_ratio > 1.000001:
            raise ValueError("启用的资金分配合计不能超过 100%")
        allocation.allocation_ratio = allocation_ratio
        allocation.enabled = enabled
        if not enabled:
            for task in self.tasks:
                if task.symbol == allocation.symbol:
                    self.stop(task.id)
        self.save()

    def remove_allocation(self, symbol: str):
        allocation = self.allocation_for(symbol, enabled_only=False)
        if not allocation:
            return
        related = [task for task in self.tasks if task.symbol == allocation.symbol]
        if any(task.status in (RUNNING, EVALUATING) for task in related):
            raise ValueError("请先停止该交易对的自动化任务")
        self.tasks = [
            task for task in self.tasks if task.symbol != allocation.symbol
        ]
        self.allocations = [
            item for item in self.allocations
            if item.symbol != allocation.symbol
        ]
        self.save()

    def total_allocation(self) -> float:
        return sum(
            item.allocation_ratio for item in self.allocations if item.enabled
        )

    def running_count(self) -> int:
        return sum(task.status in (RUNNING, EVALUATING) for task in self.tasks)

    def validate_allocations(self):
        seen = set()
        for allocation in self.allocations:
            self._validate_allocation(allocation)
            if allocation.symbol in seen:
                raise ValueError(f"交易对重复：{allocation.symbol}")
            seen.add(allocation.symbol)
        if self.total_allocation() > 1.000001:
            raise ValueError("启用的资金分配合计不能超过 100%")
        for task in self.tasks:
            self._validate_task(task)
            if not self.allocation_for(task.symbol, enabled_only=False):
                raise ValueError(f"任务交易对未配置资金：{task.symbol}")

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        return str(symbol).upper().replace("/", "").replace("-", "").strip()

    @classmethod
    def _validate_allocation(cls, allocation: InvestmentAllocation):
        allocation.symbol = cls.normalize_symbol(allocation.symbol)
        if not re.fullmatch(r"[A-Z0-9]{2,16}USDT", allocation.symbol):
            raise ValueError("请输入有效的 USDT 交易对，例如 ADAUSDT")
        if not 0 < allocation.allocation_ratio <= 1:
            raise ValueError("资金分配必须在 0% 到 100% 之间")

    @classmethod
    def _validate_task(cls, task: AutomationTask):
        task.symbol = cls.normalize_symbol(task.symbol)
        if not re.fullmatch(r"[A-Z0-9]{2,16}USDT", task.symbol):
            raise ValueError(f"不支持的交易对：{task.symbol}")
        if task.strategy not in {
            "AUTO", "TRENDING", "RANGING", "BREAKOUT", "REVERSAL", "EXTREME"
        }:
            raise ValueError("未知策略")
        if task.direction not in {"BOTH", "LONG", "SHORT"}:
            raise ValueError("未知交易方向")
        if not 0 < task.per_trade_ratio <= 1:
            raise ValueError("单次使用比例必须在 0% 到 100% 之间")
        if task.interval_seconds < 15:
            raise ValueError("执行周期不能少于 15 秒")
        if task.max_trades_per_day < 1:
            raise ValueError("每日最大执行次数至少为 1")
