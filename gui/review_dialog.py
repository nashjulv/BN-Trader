"""
复盘对话框

强制复盘时弹出的表单对话框。
"""

from datetime import datetime

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QTextEdit, QComboBox, QPushButton, QGroupBox,
                               QMessageBox, QScrollArea)
from PyQt6.QtCore import Qt

from gui.styles import Theme


class ReviewDialog(QDialog):
    """复盘对话框"""

    def __init__(self, reason: str = "", parent=None):
        super().__init__(parent)
        self.reason = reason
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("强制复盘")
        self.setMinimumSize(500, 600)
        t = Theme.colors()
        self.setStyleSheet(
            f"QDialog {{ background-color: {t['bg_main']}; }}")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 警告标题
        warning_label = QLabel("⚠️ 交易已暂停 - 需要完成复盘")
        warning_label.setStyleSheet(
            f"color: {Theme.c('danger')}; font-size: 18px; font-weight: bold;"
        )
        warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning_label)

        # 触发原因
        reason_group = QGroupBox("触发原因")
        reason_layout = QVBoxLayout(reason_group)
        reason_text = QLabel(self.reason)
        reason_text.setStyleSheet(f"color: {Theme.c('warning')}; font-size: 14px;")
        reason_text.setWordWrap(True)
        reason_layout.addWidget(reason_text)
        layout.addWidget(reason_group)

        # 错误分析
        mistake_group = QGroupBox("1. 错误分析")
        mistake_layout = QVBoxLayout(mistake_group)
        self.mistake_edit = QTextEdit()
        self.mistake_edit.setPlaceholderText(
            "请分析导致亏损的原因：\n"
            "- 是否违反了交易规则？\n"
            "- 是否受到情绪影响？\n"
            "- 是否忽略了市场信号？\n"
            "- 仓位是否过大？"
        )
        self.mistake_edit.setMinimumHeight(100)
        mistake_layout.addWidget(self.mistake_edit)
        layout.addWidget(mistake_group)

        # 市场分析
        market_group = QGroupBox("2. 市场分析")
        market_layout = QVBoxLayout(market_group)
        self.market_edit = QTextEdit()
        self.market_edit.setPlaceholderText(
            "描述当前市场状况：\n"
            "- 当时的行情场景是什么？\n"
            "- 是否有未预见的市场变化？\n"
            "- 技术指标是否给出了正确信号？"
        )
        self.market_edit.setMinimumHeight(80)
        market_layout.addWidget(self.market_edit)
        layout.addWidget(market_group)

        # 情绪状态
        emotion_layout = QHBoxLayout()
        emotion_layout.addWidget(QLabel("2.5. 交易时的情绪状态:"))
        self.emotion_combo = QComboBox()
        self.emotion_combo.addItems([
            "选择情绪状态...",
            "冷静理性",
            "焦虑紧张",
            "兴奋贪婪",
            "恐惧恐慌",
            "急躁冲动",
            "疲惫倦怠",
            "自信果断",
            "犹豫不决"
        ])
        emotion_layout.addWidget(self.emotion_combo)
        layout.addLayout(emotion_layout)

        # 改进计划
        improve_group = QGroupBox("3. 改进计划")
        improve_layout = QVBoxLayout(improve_group)
        self.improve_edit = QTextEdit()
        self.improve_edit.setPlaceholderText(
            "制定具体的改进措施：\n"
            "- 下次遇到类似情况应该怎么做？\n"
            "- 需要调整哪些交易参数？\n"
            "- 需要学习哪些知识？\n"
            "- 是否需要暂时降低仓位？"
        )
        self.improve_edit.setMinimumHeight(100)
        improve_layout.addWidget(self.improve_edit)
        layout.addWidget(improve_group)

        # 经验教训
        lesson_group = QGroupBox("4. 经验教训")
        lesson_layout = QVBoxLayout(lesson_group)
        self.lesson_edit = QTextEdit()
        self.lesson_edit.setPlaceholderText(
            "总结本次交易的核心教训：\n"
            "- 最重要的一个教训是什么？\n"
            "- 这个教训如何应用到未来交易中？"
        )
        self.lesson_edit.setMinimumHeight(60)
        lesson_layout.addWidget(self.lesson_edit)
        layout.addWidget(lesson_group)

        # 按钮
        btn_layout = QHBoxLayout()

        self.cancel_btn = QPushButton("暂时不提交")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        btn_layout.addStretch()

        self.submit_btn = QPushButton("提交复盘")
        self.submit_btn.setStyleSheet(
            f"background-color: {Theme.c('accent')}; "
            f"color: white; font-weight: bold; padding: 8px 24px;"
        )
        self.submit_btn.clicked.connect(self._validate_and_accept)
        btn_layout.addWidget(self.submit_btn)

        layout.addLayout(btn_layout)

    def _validate_and_accept(self):
        """验证并提交"""
        # 检查必填项
        if not self.mistake_edit.toPlainText().strip():
            QMessageBox.warning(self, "提示", "请填写错误分析")
            return

        if not self.improve_edit.toPlainText().strip():
            QMessageBox.warning(self, "提示", "请填写改进计划")
            return

        if not self.lesson_edit.toPlainText().strip():
            QMessageBox.warning(self, "提示", "请填写经验教训")
            return

        if self.emotion_combo.currentIndex() == 0:
            QMessageBox.warning(self, "提示", "请选择情绪状态")
            return

        self.accept()

    def get_data(self) -> dict:
        """获取复盘数据"""
        return {
            "trigger_reason": self.reason,
            "mistake_analysis": self.mistake_edit.toPlainText().strip(),
            "market_analysis": self.market_edit.toPlainText().strip(),
            "emotion_state": self.emotion_combo.currentText(),
            "improvement_plan": self.improve_edit.toPlainText().strip(),
            "lesson_learned": self.lesson_edit.toPlainText().strip(),
            "timestamp": datetime.now(),
        }

    def is_qualified(self) -> bool:
        """检查复盘是否合格"""
        data = self.get_data()
        # 简单检查：所有必填项都有内容
        return bool(
            data["mistake_analysis"] and
            data["improvement_plan"] and
            data["lesson_learned"] and
            data["emotion_state"] != "选择情绪状态..."
        )
