import json
from pathlib import Path

from tools.generate_help_docs import generate


ROOT = Path(__file__).resolve().parents[1]


def test_help_content_has_unique_chapters():
    data = json.loads(
        (ROOT / "docs" / "help_content.json").read_text(encoding="utf-8")
    )
    ids = [chapter["id"] for chapter in data["chapters"]]
    assert len(ids) == len(set(ids))
    assert all(chapter["sections"] for chapter in data["chapters"])


def test_generate_help_documents(tmp_path):
    outputs = generate(tmp_path)
    assert {path.name for path in outputs} == {
        "产品资料.md",
        "产品手册.md",
        "产品归档.md",
        "系统帮助.md",
        "升级与数据迁移.md",
    }
    assert "风险声明" in (tmp_path / "产品资料.md").read_text(encoding="utf-8")
    manual_text = (tmp_path / "产品手册.md").read_text(encoding="utf-8")
    assert "自动化投资任务台" in manual_text
    assert "USDC/USDT" in manual_text
    assert "研报" in manual_text
    archive_text = (tmp_path / "产品归档.md").read_text(encoding="utf-8")
    assert "当前交付基线" in archive_text
    assert "产品边界与已知待办" in archive_text
    assert "日志支持鼠标与键盘选择" in archive_text
    help_text = (tmp_path / "系统帮助.md").read_text(encoding="utf-8")
    assert "F1" in help_text
    assert "MACD（12、26、9）" in help_text
    assert "为什么数据不足时显示“震荡”" in help_text
    assert "当前参数生效状态" in help_text
    assert "单笔风险过大：3.00%" in help_text
    assert "右侧下单栏为什么不能操作" in help_text
    upgrade_text = (tmp_path / "升级与数据迁移.md").read_text(encoding="utf-8")
    assert "strategies.json" in upgrade_text
    assert "旧版本自动迁移" in upgrade_text
    assert "尚未提供应用内自动下载" in upgrade_text
