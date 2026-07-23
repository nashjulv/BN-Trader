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
    assert {path.name for path in outputs} == {"产品资料.md", "系统帮助.md"}
    assert "风险声明" in (tmp_path / "产品资料.md").read_text(encoding="utf-8")
    assert "F1" in (tmp_path / "系统帮助.md").read_text(encoding="utf-8")
