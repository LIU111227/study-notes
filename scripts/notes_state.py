#!/usr/bin/env python3
"""study-notes 状态管理 —— 游标与"上次全量审查"时间。

状态文件：<vault>/.study-notes/state.json（vault 取自 ~/.config/study-notes/config.json）
结构：{"sessions": {"<agent>:<session_id>": {"cursor": "..."}}, "last_review": "ISO日期"}

用法：
  python3 notes_state.py get-cursor claude:<sid>
  python3 notes_state.py set-cursor claude:<sid> <cursor>
  python3 notes_state.py review-due          # {"due": true/false, "days_since": N}
  python3 notes_state.py mark-reviewed
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime

REVIEW_INTERVAL_DAYS = 7

CONFIG_OVERRIDE = []  # 由 CLI --config 注入


def config_path() -> str:
    if CONFIG_OVERRIDE:
        return CONFIG_OVERRIDE[-1]
    if os.environ.get("STUDY_NOTES_CONFIG"):
        return os.environ["STUDY_NOTES_CONFIG"]
    return os.path.expanduser("~/.config/study-notes/config.json")


def _paths() -> tuple[str, str]:
    cfg = {}
    try:
        with open(config_path(), encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        pass
    vault = cfg.get("vault") or os.path.expanduser("~/ObsidianLearning")
    state = os.path.join(vault, ".study-notes", "state.json")
    os.makedirs(os.path.dirname(state), exist_ok=True)
    return state, vault


def _load(state: str) -> dict:
    try:
        with open(state, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sessions": {}, "last_review": ""}


def _save(state: str, data: dict) -> None:
    with open(state, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    args = sys.argv[1:]
    if "--config" in args:
        i = args.index("--config")
        if i + 1 < len(args):
            CONFIG_OVERRIDE.append(args[i + 1])
            args = args[:i] + args[i + 2:]
    sys.argv = [sys.argv[0]] + args
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    state, _ = _paths()
    data = _load(state)

    if cmd == "get-cursor" and len(sys.argv) == 3:
        print((data.get("sessions") or {}).get(sys.argv[2], {}).get("cursor") or "")
    elif cmd == "set-cursor" and len(sys.argv) == 4:
        data.setdefault("sessions", {})[sys.argv[2]] = {"cursor": sys.argv[3]}
        _save(state, data)
        print(json.dumps({"ok": True}))
    elif cmd == "review-due":
        last = data.get("last_review") or ""
        days = None
        if last:
            try:
                days = (date.today() - datetime.fromisoformat(last).date()).days
            except Exception:
                days = None
        due = last == "" or days is None or days >= REVIEW_INTERVAL_DAYS
        print(json.dumps({"due": due, "days_since": days}, ensure_ascii=False))
    elif cmd == "mark-reviewed":
        data["last_review"] = date.today().isoformat()
        _save(state, data)
        print(json.dumps({"ok": True, "last_review": data["last_review"]}))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
