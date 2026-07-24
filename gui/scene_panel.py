"""
行情场景卡片 — 主界面左侧紧凑卡片，含雷达图
"""

import math
from typing import Dict, Optional

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                          QPainterPath, QPolygonF)

from gui.styles import Theme, SCENE_COLORS, SCENE_INFO

# 雷达图五个维度的顺序（顺时针，从顶部开始）
_RADAR_KEYS  = ["TRENDING", "BREAKOUT", "EXTREME", "REVERSAL", "RANGING"]
_RADAR_NAMES = {k: SCENE_INFO[k]["name"] for k in _RADAR_KEYS}
_RADAR_COLORS = {k: QColor(SCENE_COLORS[k]) for k in _RADAR_KEYS}


class _RadarWidget(QWidget):
    """五边形雷达图 —— 展示五种场景的匹配得分"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scores: Dict[str, float] = {}
        self._dominant: str = ""
        self.setMinimumSize(180, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

    def set_scores(self, scores: Dict[str, float], dominant: str):
        self._scores = dict(scores)
        self._dominant = dominant
        self.update()

    # ---------- 绘制 ----------

    def paintEvent(self, _):
        if not self._scores:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        t = Theme.colors()
        dark = Theme.is_dark()
        w = self.width()
        h = self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 36  # 留出标签空间

        n = len(_RADAR_KEYS)
        vertices = self._polygon(cx, cy, radius, n)

        # ---- 网格 ----
        grid_pen = QPen(QColor(t["border"]), 1)
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        for level in (0.2, 0.4, 0.6, 0.8, 1.0):
            ring = self._polygon(cx, cy, radius * level, n)
            p.setPen(grid_pen if level < 1.0 else QPen(QColor(t["border"]), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in ring]))

        # ---- 轴线 ----
        p.setPen(QPen(QColor(t["border"]), 1))
        for vx, vy in vertices:
            p.drawLine(QPointF(cx, cy), QPointF(vx, vy))

        # ---- 数据区域（半透明填充） ----
        data_pts = [QPointF(cx + radius * self._scores.get(k, 0) * math.cos(a),
                             cy - radius * self._scores.get(k, 0) * math.sin(a))
                     for k, a in self._angles(cx, cy, radius, n)]
        data_poly = QPolygonF(data_pts)

        dominant_color = _RADAR_COLORS.get(self._dominant, QColor(t["accent"]))
        fill_color = QColor(dominant_color)
        fill_color.setAlpha(40 if dark else 55)
        p.setBrush(QBrush(fill_color))
        p.setPen(QPen(dominant_color, 2))
        p.drawPolygon(data_poly)

        # ---- 数据点 ----
        for pt, key in zip(data_pts, _RADAR_KEYS):
            c = _RADAR_COLORS.get(key, QColor(t["accent"]))
            p.setBrush(QBrush(c))
            p.setPen(QPen(c.darker(120), 1))
            p.drawEllipse(pt, 4, 4)

        # ---- 标签 ----
        font = QFont()
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Medium if not dark else QFont.Weight.Normal)
        p.setFont(font)

        for key, (vx, vy) in zip(_RADAR_KEYS, vertices):
            score = self._scores.get(key, 0)
            label = _RADAR_NAMES.get(key, key)
            text = f"{label}\n{score:.0%}"

            # 根据顶点相对圆心的位置决定文字对齐
            dx, dy = vx - cx, -(vy - cy)
            p.setPen(QPen(QColor(t["text_secondary"]), 1))
            self._draw_label(p, QPointF(vx, vy), dx, dy, text)

        p.end()

    def _draw_label(self, painter: QPainter, pt: QPointF,
                     dx: float, dy: float, text: str):
        """在顶点外侧绘制标签，自动避开图形。"""
        lines = text.split("\n")
        fm = painter.fontMetrics()
        line_h = fm.height()
        total_h = line_h * len(lines)
        max_w = max(fm.horizontalAdvance(line) for line in lines)

        offset = 16
        nx = dx / math.hypot(dx, dy) if dx or dy else 0
        ny = dy / math.hypot(dx, dy) if dx or dy else -1

        # 文字框左上角
        bx = pt.x() + nx * offset
        by = pt.y() + ny * offset

        # 水平对齐
        if abs(nx) < 0.3:
            bx -= max_w / 2
        elif nx > 0:
            pass
        else:
            bx -= max_w

        # 垂直对齐
        if abs(ny) < 0.3:
            by -= total_h / 2
        elif ny > 0:
            pass
        else:
            by -= total_h

        painter.setPen(QPen(QColor(Theme.c("text_secondary")), 1))
        for i, line in enumerate(lines):
            painter.drawText(QRectF(bx, by + i * line_h, max_w + 8, line_h),
                            Qt.AlignmentFlag.AlignCenter, line)

    # ---------- 几何工具 ----------

    def _polygon(self, cx, cy, r, n):
        """计算 n 边形的顶点列表，从顶部开始顺时针。"""
        pts = []
        for i in range(n):
            angle = math.radians(-90 + i * 360 / n)
            pts.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
        return pts

    def _angles(self, cx, cy, r, n):
        """返回 (key, angle_rad) ，从顶部开始顺时针。"""
        for i, key in enumerate(_RADAR_KEYS):
            yield key, math.radians(-90 + i * 360 / n)


class ScenePanel(QWidget):
    """行情场景卡片 — 雷达图 + 主导场景信息"""

    def __init__(self, compact: bool = True):
        super().__init__()
        self.compact = compact
        self.current_scene = "RANGING"
        self._scene_scores: Dict[str, float] = {}
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("cardFrame")
        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # 标题行
        hdr = QHBoxLayout()
        self._title = QLabel("当前行情场景")
        self._title.setObjectName("sectionTitle")
        hdr.addWidget(self._title)
        hdr.addStretch()
        layout.addLayout(hdr)

        # 主导场景名 + 建议
        row = QHBoxLayout()
        self.scene_name_label = QLabel("--")
        self.scene_name_label.setStyleSheet("font-size:15px; font-weight:700;")
        row.addWidget(self.scene_name_label)
        row.addStretch()
        self.confidence_label = QLabel("--")
        self.confidence_label.setStyleSheet("font-size:15px; font-weight:700;")
        row.addWidget(self.confidence_label)
        layout.addLayout(row)

        self.action_label = QLabel("建议: --")
        self.action_label.setObjectName("captionLabel")
        self.action_label.setWordWrap(True)
        layout.addWidget(self.action_label)

        # 雷达图
        self._radar = _RadarWidget()
        layout.addWidget(self._radar)

        # 场景快捷切换按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.scene_buttons = {}
        for st in _RADAR_KEYS:
            info = SCENE_INFO[st]
            btn = QPushButton(info["name"][:2])
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(info["name"])
            btn.clicked.connect(lambda _, s=st: self._on_scene_clicked(s))
            self.scene_buttons[st] = btn
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        # 非紧凑模式下的补充信息
        if not self.compact:
            self.trend_label = QLabel("趋势: --")
            self.volatility_label = QLabel("波动率: --")
            self.volume_label = QLabel("成交量: --")
            for lbl in [self.trend_label, self.volatility_label, self.volume_label]:
                lbl.setObjectName("captionLabel")
                layout.addWidget(lbl)
        else:
            self.trend_label = self.volatility_label = self.volume_label = None

        root.addWidget(self._card)

    # ---------- 主题 ----------

    def _refresh_theme(self):
        t = Theme.colors()
        self._card.setStyleSheet(Theme.card_style())
        color = SCENE_COLORS.get(self.current_scene, t["accent"])
        self.scene_name_label.setStyleSheet(
            f"font-size:15px; font-weight:700; color:{color};")
        self.confidence_label.setStyleSheet(
            f"font-size:15px; font-weight:700; color:{color};")
        for st, btn in self.scene_buttons.items():
            c = SCENE_COLORS.get(st, "#888")
            active = st == self.current_scene
            if active:
                btn.setStyleSheet(
                    f"background:{c}; color:#fff; border:none; "
                    f"border-radius:4px; font-size:11px; font-weight:600; padding:2px 6px;")
            else:
                btn.setStyleSheet(
                    f"background:transparent; color:{t['text_secondary']}; "
                    f"border:1px solid {t['border']}; border-radius:4px; "
                    f"font-size:11px; padding:2px 6px;")

    # ---------- 数据更新 ----------

    def update_scene(self, scene_data: Dict):
        if not scene_data:
            return
        self.current_scene = scene_data.get("type", "RANGING")
        info = SCENE_INFO.get(self.current_scene, SCENE_INFO["RANGING"])
        conf = scene_data.get("confidence", 0)
        self.scene_name_label.setText(f"{info['icon']} {info['name']}")
        self.confidence_label.setText(f"{conf:.0%}")
        self.action_label.setText(f"建议: {info['tip']}")

        # 雷达图
        scores = scene_data.get("scene_scores")
        if scores:
            self._scene_scores = dict(scores)
            self._radar.set_scores(scores, self.current_scene)

        if self.trend_label:
            self.trend_label.setText(f"趋势: {scene_data.get('trend_strength', 0):.2f}")
            self.volatility_label.setText(f"波动率: {scene_data.get('volatility', 0):.2f}")
            self.volume_label.setText(f"成交量变化: {scene_data.get('volume_change', 0):.2%}")

        self._refresh_theme()

    # ---------- 手动切换 ----------

    def _on_scene_clicked(self, st: str):
        info = SCENE_INFO.get(st, {})
        self.current_scene = st
        self.scene_name_label.setText(f"{info.get('icon','')} {info.get('name','')}")
        self.confidence_label.setText("---")
        self.action_label.setText(f"手动: {info.get('tip', '')}")
        self._radar.set_scores({k: 0.0 for k in _RADAR_KEYS}, st)
        self._refresh_theme()
