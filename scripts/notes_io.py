#!/usr/bin/env python3
"""study-notes 配置与目录引导。

用法：
  python3 notes_io.py init-config --vault /mnt/d/Obsidian/doc/learning --subject 视觉
  python3 notes_io.py show                       # 打印生效配置
  python3 notes_io.py init-subject [--name 视觉] # 建学科目录 + index.md 骨架（已存在则跳过）
"""
from __future__ import annotations

import json
import os
import sys

CONFIG = os.path.expanduser("~/.config/study-notes/config.json")

INDEX_TEMPLATE = """# {subject} · 学习笔记索引

> 章节按知识脉络排序。新增章节时按前后逻辑插入合适位置，不默认加在文末。

## 章节

<!-- 每行一个主题文件：- [[文件名（不带.md）]] — 一句话说明该主题 -->

（暂无章节）
"""


def load_config() -> dict:
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    if args[0] == "init-config":
        vault = subject = None
        i = 1
        while i < len(args):
            if args[i] == "--vault" and i + 1 < len(args):
                vault = args[i + 1]; i += 2
            elif args[i] == "--subject" and i + 1 < len(args):
                subject = args[i + 1]; i += 2
            else:
                i += 1
        if not vault:
            print("需要 --vault"); return 1
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        cfg = load_config()
        cfg["vault"] = vault
        if subject:
            cfg["default_subject"] = subject
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        # 同步初始化状态目录
        os.makedirs(os.path.join(vault, ".study-notes"), exist_ok=True)
        print(json.dumps({"ok": True, "config": CONFIG, "vault": cfg["vault"],
                          "default_subject": cfg.get("default_subject", "")}, ensure_ascii=False))

    elif args[0] == "show":
        print(json.dumps(load_config(), ensure_ascii=False))

    elif args[0] == "init-subject":
        cfg = load_config()
        vault = cfg.get("vault")
        if not vault:
            print("配置不存在，先运行 init-config"); return 1
        name = None
        if "--name" in args and args.index("--name") + 1 < len(args):
            name = args[args.index("--name") + 1]
        name = name or cfg.get("default_subject")
        if not name:
            print("未指定学科名（--name 或配置 default_subject）"); return 1
        d = os.path.join(vault, name)
        os.makedirs(d, exist_ok=True)
        idx = os.path.join(d, "index.md")
        if not os.path.exists(idx):
            with open(idx, "w", encoding="utf-8") as f:
                f.write(INDEX_TEMPLATE.format(subject=name))
            print(json.dumps({"ok": True, "created": idx}, ensure_ascii=False))
        else:
            print(json.dumps({"ok": True, "exists": idx}, ensure_ascii=False))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
