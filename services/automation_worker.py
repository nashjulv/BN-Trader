"""后台执行单个自动化任务的行情获取与策略评估。"""

from PyQt6.QtCore import QThread, pyqtSignal

from indicators.technical import calculate_all_indicators
from services.automation_manager import AutomationTask
from services.binance_client import BinanceClient
from services.scene_detector import SceneDetector
from services.strategy_engine import StrategyEngine
from strategies.base import SignalType
from utils.parameter_units import strategy_runtime_params


class AutomationEvaluationWorker(QThread):
    evaluated = pyqtSignal(str, dict)

    def __init__(self, task: AutomationTask, strategy_settings: dict):
        super().__init__()
        self.task = task
        self.strategy_settings = strategy_settings

    def run(self):
        try:
            client = BinanceClient()
            klines = client.get_klines(
                self.task.symbol, self.task.timeframe, limit=100
            )
            if not klines:
                raise RuntimeError("未获取到行情数据")
            df = client.klines_to_dataframe(klines)
            df["symbol"] = self.task.symbol
            df = calculate_all_indicators(df)
            scene = SceneDetector().detect(df)

            selected = (
                scene.type if self.task.strategy == "AUTO"
                else self.task.strategy
            )
            if self.task.strategy != "AUTO" and selected != scene.type:
                self.evaluated.emit(self.task.id, {
                    "ok": True,
                    "scene": scene.type,
                    "confidence": scene.confidence,
                    "message": f"当前场景 {scene.type}，等待 {selected} 策略环境",
                })
                return

            engine = StrategyEngine()
            for scene_type, strategy in engine.strategies.items():
                values = self.strategy_settings.get(scene_type, {})
                strategy.set_params(**strategy_runtime_params(values))

            strategy = engine.strategies.get(selected)
            signal = strategy.analyze(df, scene) if strategy else None
            if not signal or signal.type == SignalType.HOLD:
                self.evaluated.emit(self.task.id, {
                    "ok": True,
                    "scene": scene.type,
                    "confidence": scene.confidence,
                    "message": (
                        signal.reason if signal else
                        f"{selected} 暂无可执行信号"
                    ),
                })
                return

            side = "BUY" if signal.type == SignalType.BUY else "SELL"
            if (
                (self.task.direction == "LONG" and side != "BUY")
                or (self.task.direction == "SHORT" and side != "SELL")
            ):
                self.evaluated.emit(self.task.id, {
                    "ok": True,
                    "scene": scene.type,
                    "confidence": scene.confidence,
                    "message": f"{side} 信号不符合任务方向限制",
                })
                return

            self.evaluated.emit(self.task.id, {
                "ok": True,
                "scene": scene.type,
                "confidence": scene.confidence,
                "message": signal.reason,
                "signal": {
                    "side": side,
                    "symbol": signal.symbol,
                    "price": signal.price,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "confidence": signal.confidence,
                    "reason": signal.reason,
                },
            })
        except Exception as error:
            self.evaluated.emit(self.task.id, {
                "ok": False,
                "message": f"评估失败：{error}",
            })
