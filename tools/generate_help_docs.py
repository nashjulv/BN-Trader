#!/usr/bin/env python3
"""从统一帮助内容生成产品资料与系统帮助 Markdown。"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "help_content.json"


def app_version() -> str:
    text = (ROOT / "config.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else "unknown"


def _list(lines, values, ordered=False):
    for index, value in enumerate(values, 1):
        marker = f"{index}." if ordered else "-"
        lines.append(f"{marker} {value}")


def product_markdown(data: dict, version: str) -> str:
    product = data["product"]
    lines = [
        f"# {product['name']} v{version} 产品资料",
        "",
        f"> {product['subtitle']}",
        "",
        "## 产品定位",
        "",
        product["summary"],
        "",
        "## 目标用户",
        "",
    ]
    _list(lines, product["audience"])
    lines.extend(["", "## 核心能力", ""])
    _list(lines, product["features"])
    lines.extend(["", "## 支持平台", ""])
    _list(lines, product["platforms"])
    lines.extend(["", "## 安全与隐私", ""])
    _list(lines, product["security"])
    lines.extend([
        "",
        "## 推荐上线流程",
        "",
        "1. 使用模拟或只读环境确认行情与账户数据。",
        "2. 设置资金、风控、持仓及策略参数。",
        "3. 用小额交易验证订单链路与日志。",
        "4. 定期复盘，并根据真实风险承受能力调整限制。",
        "",
        "## 风险声明",
        "",
        "本产品是交易辅助工具，不构成投资建议，也不保证收益。数字资产价格波动剧烈，用户应独立判断并承担交易风险。",
        "",
        "---",
        "",
        "本文档由 `tools/generate_help_docs.py` 根据 `docs/help_content.json` 自动生成，请勿直接编辑。",
        "",
    ])
    return "\n".join(lines)


def help_markdown(data: dict, version: str) -> str:
    lines = [
        f"# BN-Trader v{version} 系统帮助",
        "",
        "> 在应用内按 `F1` 可随时打开可搜索的帮助中心。",
        "",
    ]
    for number, chapter in enumerate(data["chapters"], 1):
        lines.extend([
            f"## {number}. {chapter['title']}",
            "",
            chapter["summary"],
            "",
        ])
        for section in chapter["sections"]:
            lines.extend([f"### {section['title']}", ""])
            if section.get("body"):
                lines.extend([section["body"], ""])
            if section.get("items"):
                _list(lines, section["items"])
                lines.append("")
            if section.get("steps"):
                _list(lines, section["steps"], ordered=True)
                lines.append("")
            if section.get("note"):
                lines.extend([f"> 提示：{section['note']}", ""])
    lines.extend([
        "---",
        "",
        "本文档由 `tools/generate_help_docs.py` 根据 `docs/help_content.json` 自动生成，请勿直接编辑。",
        "",
    ])
    return "\n".join(lines)


def upgrade_markdown(data: dict, version: str) -> str:
    upgrade = data["upgrade"]
    lines = [
        f"# {upgrade['title']}",
        "",
        f"适用版本：v{version}",
        "",
        upgrade["summary"],
        "",
        f"> 当前状态：{upgrade['status']}",
        "",
    ]
    for number, section in enumerate(upgrade["sections"], 1):
        lines.extend([f"## {number}. {section['title']}", ""])
        if section.get("body"):
            lines.extend([section["body"], ""])
        if section.get("items"):
            _list(lines, section["items"])
            lines.append("")
        if section.get("steps"):
            _list(lines, section["steps"], ordered=True)
            lines.append("")
        if section.get("note"):
            lines.extend([f"> 注意：{section['note']}", ""])
    lines.extend([
        "---",
        "",
        "本文档由 `tools/generate_help_docs.py` 根据 `docs/help_content.json` 自动生成，请勿直接编辑。",
        "",
    ])
    return "\n".join(lines)


def generate(output_dir: Path) -> list[Path]:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    version = app_version()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        output_dir / "产品资料.md": product_markdown(data, version),
        output_dir / "系统帮助.md": help_markdown(data, version),
        output_dir / "升级与数据迁移.md": upgrade_markdown(data, version),
    }
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
        print(f"generated: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return list(outputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "docs",
        help="Markdown 输出目录（默认：docs）",
    )
    args = parser.parse_args()
    generate(args.output_dir.resolve())


if __name__ == "__main__":
    main()
