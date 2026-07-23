"""
K线图组件

使用PyQtGraph绘制K线图，支持多种技术指标叠加显示。
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor

from gui.styles import Theme


class CandleStickItem(pg.GraphicsObject):
    """K线图形化项目"""

    def __init__(self, data: pd.DataFrame = None):
        pg.GraphicsObject.__init__(self)
        self.data = data if data is not None else pd.DataFrame()
        self.picture = None
        self.generate_picture()

    def set_data(self, data: pd.DataFrame):
        """设置数据"""
        self.data = data
        self.generate_picture()
        self.update()

    def generate_picture(self):
        """生成K线图"""
        if self.data.empty:
            self.picture = None
            return

        self.picture = pg.QtGui.QPicture()
        painter = pg.QtGui.QPainter(self.picture)

        w = 0.8
        for i, (_, bar) in enumerate(self.data.iterrows()):
            open_price = float(bar["open"])
            close_price = float(bar["close"])
            high_price = float(bar["high"])
            low_price = float(bar["low"])

            # K线颜色
            if close_price >= open_price:
                color = QColor(82, 196, 26)  # #52C41A
                body_bottom = open_price
                body_top = close_price
            else:
                color = QColor(255, 77, 79)  # #FF4D4F
                body_bottom = close_price
                body_top = open_price

            painter.setPen(pg.mkPen(color))
            painter.setBrush(pg.mkBrush(color))

            # 影线
            painter.drawLine(
                pg.QtCore.QPointF(i, low_price),
                pg.QtCore.QPointF(i, body_top)
            )
            # 实体
            painter.drawRect(
                pg.QtCore.QRectF(i - w / 2, body_bottom, w, body_top - body_bottom)
            )
            # 上方影线
            painter.drawLine(
                pg.QtCore.QPointF(i, body_bottom),
                pg.QtCore.QPointF(i, high_price)
            )

        painter.end()

    def paint(self, painter, option, widget):
        if self.picture:
            painter.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        if self.picture:
            return pg.QtCore.QRectF(self.picture.boundingRect())
        return pg.QtCore.QRectF(0, 0, 0, 0)


class ChartWidget(QWidget):
    """K线图组件"""

    request_data = pyqtSignal(str, str)  # (symbol, timeframe)

    def __init__(self):
        super().__init__()

        self.symbol = "BTCUSDT"
        self.timeframe = "15m"
        self.df = pd.DataFrame()
        self.indicators = {}
        self._empty_text = None

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 顶部控制栏
        control_bar = QHBoxLayout()
        control_bar.setSpacing(8)

        title = QLabel("K线图")
        title.setObjectName("sectionTitle")
        control_bar.addWidget(title)

        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(
            ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"])
        self.symbol_combo.setFixedWidth(110)
        self.symbol_combo.currentTextChanged.connect(self._on_symbol_changed)
        control_bar.addWidget(self.symbol_combo)

        # K线周期快捷按钮风格通过下拉
        self.tf_combo = QComboBox()
        self.tf_combo.addItems(["1m", "5m", "15m", "30m", "1h", "4h", "1d"])
        self.tf_combo.setCurrentText("15m")
        self.tf_combo.setFixedWidth(72)
        self.tf_combo.currentTextChanged.connect(self._on_timeframe_changed)
        control_bar.addWidget(self.tf_combo)

        self.price_label = QLabel("---")
        self.price_label.setStyleSheet(
            f"color: {Theme.c('accent')}; font-size: 16px; font-weight:700;")
        control_bar.addWidget(self.price_label)

        control_bar.addStretch()

        self.indicator_combo = QComboBox()
        self.indicator_combo.addItems(["无", "MA", "EMA", "布林带", "MACD", "RSI"])
        self.indicator_combo.setFixedWidth(90)
        self.indicator_combo.currentTextChanged.connect(self._on_indicator_changed)
        control_bar.addWidget(self.indicator_combo)

        layout.addLayout(control_bar)

        # 图表区域
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(QColor(Theme.c('bg_main')))
        self.plot_widget.setLabel("left", "价格")
        self.plot_widget.setLabel("bottom", "时间")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # K线项
        self.candle_item = CandleStickItem()
        self.plot_widget.addItem(self.candle_item)
        self._empty_text = pg.TextItem(
            "等待行情数据…", color=Theme.c("text_secondary"), anchor=(0.5, 0.5))
        self._empty_text.setPos(0, 0)
        self.plot_widget.addItem(self._empty_text)
        self.plot_widget.hideAxis("left")
        self.plot_widget.hideAxis("bottom")

        # 指标线
        self.indicator_lines: Dict[str, pg.PlotDataItem] = {}

        layout.addWidget(self.plot_widget)

        # 成交量副图
        self.volume_plot = pg.PlotWidget()
        self.volume_plot.setMaximumHeight(110)
        self.volume_plot.setBackground(QColor(Theme.c("bg_main")))
        self.volume_plot.setLabel("left", "成交量")
        self.volume_plot.showGrid(x=True, y=True, alpha=0.2)
        self.volume_plot.setXLink(self.plot_widget)
        self.volume_plot.hide()
        layout.addWidget(self.volume_plot)

        # MACD / RSI 副图，按需显示
        self.indicator_plot = pg.PlotWidget()
        self.indicator_plot.setMaximumHeight(120)
        self.indicator_plot.setBackground(QColor(Theme.c("bg_main")))
        self.indicator_plot.showGrid(x=True, y=True, alpha=0.2)
        self.indicator_plot.setXLink(self.plot_widget)
        self.indicator_plot.hide()
        layout.addWidget(self.indicator_plot)

    def _apply_theme(self):
        t = Theme.colors()
        for plot in [self.plot_widget, self.volume_plot, self.indicator_plot]:
            plot.setBackground(QColor(t['chart_bg']))
            for axis_name in ("left", "bottom"):
                axis = plot.getAxis(axis_name)
                axis.setPen(pg.mkPen(t["border"]))
                axis.setTextPen(pg.mkPen(t["text_secondary"]))
        if self._empty_text:
            self._empty_text.setColor(QColor(t["text_secondary"]))

    def update_data(self, df: pd.DataFrame):
        """更新K线数据"""
        if df.empty:
            return

        self.df = df
        if self._empty_text:
            self._empty_text.hide()
        self.plot_widget.showAxis("left")
        self.plot_widget.showAxis("bottom")
        self.candle_item.set_data(df)
        self.volume_plot.clear()
        self.volume_plot.show()
        volumes = df["volume"].to_numpy(dtype=float)
        opens = df["open"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)
        x = np.arange(len(df))
        up = closes >= opens
        if up.any():
            self.volume_plot.addItem(pg.BarGraphItem(
                x=x[up], height=volumes[up], width=0.8,
                brush=pg.mkBrush("#52C41A88"), pen=None))
        if (~up).any():
            self.volume_plot.addItem(pg.BarGraphItem(
                x=x[~up], height=volumes[~up], width=0.8,
                brush=pg.mkBrush("#FF4D4F88"), pen=None))

        # 更新价格显示
        if not df.empty:
            last_price = df["close"].iloc[-1]
            self.price_label.setText(f"{last_price:.2f}")

        # 自动缩放
        self.plot_widget.autoRange()

    def add_indicator(self, name: str, data: np.ndarray, color: str = "#FF9800"):
        """添加指标线"""
        # 移除旧的
        if name in self.indicator_lines:
            self.plot_widget.removeItem(self.indicator_lines[name])

        # 添加新的
        pen = pg.mkPen(color=color, width=1)
        line = pg.PlotDataItem(data, pen=pen)
        self.plot_widget.addItem(line)
        self.indicator_lines[name] = line

    def clear_indicators(self):
        """清除指标线"""
        for line in self.indicator_lines.values():
            self.plot_widget.removeItem(line)
        self.indicator_lines.clear()

    def _on_symbol_changed(self, symbol: str):
        """交易对变化"""
        self.symbol = symbol
        self.request_data.emit(symbol, self.timeframe)

    def _on_timeframe_changed(self, timeframe: str):
        """K线周期变化"""
        self.timeframe = timeframe
        self.request_data.emit(self.symbol, timeframe)

    def _on_indicator_changed(self, indicator: str):
        """指标选择变化"""
        self.clear_indicators()
        self.indicator_plot.clear()
        self.indicator_plot.hide()

        if self.df.empty:
            return

        close = self.df["close"].values if "close" in self.df.columns else None
        if close is None:
            return

        if indicator == "MA":
            # 5, 10, 20周期均线
            for period, color in [(5, "#FF9800"), (10, "#2196F3"), (20, "#9C27B0")]:
                if len(close) >= period:
                    ma = np.convolve(close.astype(float), np.ones(period) / period, mode="valid")
                    self.add_indicator(f"MA{period}", ma, color)

        elif indicator == "EMA":
            for period, color in [(12, "#FF9800"), (26, "#2196F3")]:
                if len(close) >= period:
                    ema_values = self._calc_ema(close.astype(float), period)
                    self.add_indicator(f"EMA{period}", ema_values, color)

        elif indicator == "布林带":
            if len(close) >= 20:
                from indicators.technical import bollinger_bands
                upper, middle, lower = bollinger_bands(close.astype(float), 20, 2)
                self.add_indicator("BB上轨", upper, "#FF9800")
                self.add_indicator("BB中轨", middle, "#2196F3")
                self.add_indicator("BB下轨", lower, "#FF9800")

        elif indicator == "RSI":
            from indicators.technical import rsi
            values = rsi(close.astype(float), 14)
            self.indicator_plot.show()
            self.indicator_plot.setLabel("left", "RSI")
            self.indicator_plot.addItem(
                pg.PlotDataItem(values, pen=pg.mkPen("#722ED1", width=1.5)))
            self.indicator_plot.addLine(y=70, pen=pg.mkPen("#FF4D4F", style=Qt.PenStyle.DashLine))
            self.indicator_plot.addLine(y=30, pen=pg.mkPen("#52C41A", style=Qt.PenStyle.DashLine))
            self.indicator_plot.setYRange(0, 100)

        elif indicator == "MACD":
            from indicators.technical import macd
            macd_line, signal_line, hist = macd(close.astype(float))
            self.indicator_plot.show()
            self.indicator_plot.setLabel("left", "MACD")
            self.indicator_plot.addItem(
                pg.PlotDataItem(macd_line, pen=pg.mkPen("#1677FF", width=1.5)))
            self.indicator_plot.addItem(
                pg.PlotDataItem(signal_line, pen=pg.mkPen("#FA8C16", width=1.5)))
            hx = np.arange(len(hist))
            positive = hist >= 0
            self.indicator_plot.addItem(pg.BarGraphItem(
                x=hx[positive], height=hist[positive], width=0.7,
                brush=pg.mkBrush("#52C41A88"), pen=None))
            self.indicator_plot.addItem(pg.BarGraphItem(
                x=hx[~positive], height=hist[~positive], width=0.7,
                brush=pg.mkBrush("#FF4D4F88"), pen=None))

    def _calc_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """计算EMA"""
        alpha = 2 / (period + 1)
        ema_values = np.zeros_like(data)
        ema_values[0] = data[0]
        for i in range(1, len(data)):
            ema_values[i] = alpha * data[i] + (1 - alpha) * ema_values[i - 1]
        return ema_values
