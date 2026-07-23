"""用户设置的迁移、合并与原子持久化工具。"""

import json
import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Iterable


def migrate_legacy_file(target: Path, legacy_paths: Iterable[Path]) -> bool:
    """目标不存在时复制第一份可用旧配置，保留旧文件作为回退。"""
    if target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    for legacy in legacy_paths:
        legacy = Path(legacy)
        if legacy == target or not legacy.is_file():
            continue
        shutil.copy2(legacy, target)
        _restrict_permissions(target)
        return True
    return False


def deep_merge_defaults(saved: dict, defaults: dict) -> dict:
    """保留客户值，并递归补充新版本增加的默认字段。"""
    merged = deepcopy(saved)
    for key, default_value in defaults.items():
        if key not in merged:
            merged[key] = deepcopy(default_value)
        elif isinstance(default_value, dict) and isinstance(merged[key], dict):
            merged[key] = deep_merge_defaults(merged[key], default_value)
    return merged


def load_json_settings(
    target: Path,
    defaults: dict,
    legacy_paths: Iterable[Path] = (),
) -> dict:
    migrate_legacy_file(target, legacy_paths)
    try:
        saved = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            return deep_merge_defaults(saved, defaults)
    except (OSError, json.JSONDecodeError):
        pass
    return deepcopy(defaults)


def save_json_settings(target: Path, data: dict, *, sensitive=False):
    """同目录临时写入后原子替换，并为上一版本保留 .bak。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, backup)
        if sensitive:
            _restrict_permissions(backup)

    payload = dict(data)
    payload.setdefault("_schema_version", 1)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if sensitive:
            _restrict_permissions(temp_path)
        temp_path.replace(target)
        if sensitive:
            _restrict_permissions(target)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _restrict_permissions(path: Path):
    try:
        path.chmod(0o600)
    except OSError:
        pass
