#!/usr/bin/env python3
"""study-notes fetcher — 探测宿主 agent，拉取"当前会话"游标之后的新消息。

输出 JSON（stdout）：
  {agent, session_id, session_title, new_count, overlap, messages, cursor}
  messages: [{role, text, id}]（按时间顺序）
  cursor:   最后一条消息的 id（处理成功后应调用 notes_state.py set-cursor 保存）

用法：
  python3 fetch_new.py                     # 自动探测宿主
  python3 fetch_new.py --agent claude      # 强制 Claude Code 模式
  python3 fetch_new.py --agent deeptutor   # 强制 DeepTutor 模式
  python3 fetch_new.py --cursor <id>       # 显式游标（缺省从 notes_state 读）
  python3 fetch_new.py --max-chars 20000   # 输出总量上限（默认 24000）
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import urllib.request

DEEPTUTOR_API = "http://127.0.0.1:8001"
OVERLAP_N = 2          # 游标前的衔接消息条数
MSG_CHAR_CAP = 4000    # 单条消息截断上限


# ---------------------------------------------------------------- state/config

def config_path() -> str:
    return os.path.expanduser("~/.config/study-notes/config.json")


def state_path() -> str:
    cfg = {}
    try:
        with open(config_path(), encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        pass
    vault = cfg.get("vault") or os.path.expanduser("~/ObsidianLearning")
    return os.path.join(vault, ".study-notes", "state.json")


def load_cursor(key: str) -> str:
    try:
        with open(state_path(), encoding="utf-8") as f:
            return (json.load(f).get("sessions") or {}).get(key, {}).get("cursor") or ""
    except Exception:
        return ""


# ---------------------------------------------------------------- detection

def detect_agent(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    env = os.environ
    if env.get("CLAUDECODE") == "1" or env.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude"
    try:
        with urllib.request.urlopen(DEEPTUTOR_API + "/api/sessions", timeout=2) as r:
            if r.status == 200:
                return "deeptutor"
    except Exception:
        pass
    if glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
        return "claude"
    return None


# ---------------------------------------------------------------- claude code

CLAUDE_SKIP_PREFIXES = ("<command", "<local-command", "<system-reminder", "Caveat:")


def _claude_msg_text(entry: dict) -> str:
    """提取一条 user/assistant 事件的纯文本；工具结果/子链/元消息返回空串。"""
    if entry.get("isSidechain") or entry.get("isMeta"):
        return ""
    msg = entry.get("message") or {}
    content = msg.get("content")
    parts: list[str] = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        has_tool_result = False
        for blk in content:
            if not isinstance(blk, dict):
                continue
            t = blk.get("type")
            if t == "tool_result":
                has_tool_result = True
            elif t == "text":
                parts.append(str(blk.get("text") or ""))
        if has_tool_result:
            return ""
    text = "\n".join(p for p in parts if p).strip()
    if not text or text.startswith(CLAUDE_SKIP_PREFIXES):
        return ""
    return text


def fetch_claude(cursor: str, max_chars: int) -> dict:
    projects_root = os.path.expanduser("~/.claude/projects")
    cwd_dir = os.getcwd().replace("/", "-")
    all_files = glob.glob(os.path.join(projects_root, "*", "*.jsonl"))
    in_cwd = [f for f in all_files if os.path.basename(os.path.dirname(f)) == cwd_dir]
    # 当前会话文件 = （本项目目录下的，否则全部）最近修改的 jsonl
    files = sorted(in_cwd or all_files, key=os.path.getmtime, reverse=True)
    if not files:
        return {"error": "no_transcript", "detail": "未找到 Claude Code transcript"}
    path = files[0]
    session_id = os.path.splitext(os.path.basename(path))[0]
    if not cursor:
        cursor = load_cursor(f"claude:{session_id}")

    msgs: list[dict] = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("type") not in ("user", "assistant"):
                continue
            text = _claude_msg_text(d)
            if not text:
                continue
            msgs.append({
                "role": "user" if d.get("type") == "user" else "assistant",
                "text": text,
                "id": d.get("uuid") or "",
                "ts": d.get("timestamp") or "",
            })

    idx = -1
    if cursor:
        for i, m in enumerate(msgs):
            if m["id"] == cursor:
                idx = i
                break
    overlap = msgs[max(0, idx - OVERLAP_N + 1):idx + 1] if idx >= 0 else []
    new = msgs[idx + 1:] if idx >= 0 else msgs  # 首次（无游标）→ 本会话全部
    return _pack("claude", session_id, session_id, overlap, new, max_chars)


# ---------------------------------------------------------------- deeptutor

def _dt_get(path: str) -> dict:
    with urllib.request.urlopen(DEEPTUTOR_API + path, timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_deeptutor(a_cursor: str, max_chars: int, session_id: str | None) -> dict:
    cursor = a_cursor
    try:
        listing = _dt_get("/api/sessions")
    except Exception as e:
        return {"error": "deeptutor_unreachable", "detail": str(e)[:200]}
    sessions = listing.get("sessions") or []
    if not sessions:
        return {"error": "no_sessions", "detail": "DeepTutor 中还没有任何会话"}
    if not session_id:
        sessions.sort(key=lambda s: float(s.get("updated_at") or 0), reverse=True)
        session_id = sessions[0].get("id")
    title = ""
    for s in sessions:
        if s.get("id") == session_id:
            title = s.get("title") or ""
            break
    try:
        detail = _dt_get(f"/api/sessions/{session_id}")
    except Exception as e:
        return {"error": "session_fetch_failed", "detail": str(e)[:200]}
    if not a_cursor and session_id:
        cursor = load_cursor(f"deeptutor:{session_id}")

    msgs = []
    for m in detail.get("messages") or []:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content")
        if not isinstance(content, str):
            continue
        content = content.strip()
        if not content or content.startswith("<"):
            continue
        msgs.append({
            "role": role,
            "text": content,
            "id": str(m.get("id") or ""),
            "ts": str(m.get("created_at") or ""),
        })

    idx = -1
    if cursor:
        for i, m in enumerate(msgs):
            if m["id"] == cursor:
                idx = i
                break
    overlap = msgs[max(0, idx - OVERLAP_N + 1):idx + 1] if idx >= 0 else []
    new = msgs[idx + 1:] if idx >= 0 else msgs
    return _pack("deeptutor", session_id, title, overlap, new, max_chars)


# ---------------------------------------------------------------- common

def _pack(agent: str, sid: str, title: str, overlap: list, new: list, max_chars: int) -> dict:
    cursor = new[-1]["id"] if new else (overlap[-1]["id"] if overlap else "")
    total = 0
    out, truncated = [], False
    for m in new:
        t = m["text"][:MSG_CHAR_CAP]
        if total + len(t) > max_chars:
            t = t[: max(0, max_chars - total)]
            truncated = True
        total += len(t)
        out.append({"role": m["role"], "text": t, "id": m["id"]})
        if truncated:
            break
    return {
        "agent": agent,
        "session_id": sid,
        "session_title": title,
        "new_count": len(new),
        "truncated": truncated,
        "overlap": [{"role": m["role"], "text": m["text"][:800]} for m in overlap],
        "messages": out,
        "cursor": cursor,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=["claude", "deeptutor"])
    ap.add_argument("--session-id")
    ap.add_argument("--cursor")
    ap.add_argument("--max-chars", type=int, default=24000)
    a = ap.parse_args()

    agent = detect_agent(a.agent)
    if agent is None:
        print(json.dumps({"error": "agent_unknown",
                          "detail": "既探测不到 Claude Code 也探测不到 DeepTutor"}, ensure_ascii=False))
        return 1
    key = None
    if a.session_id:
        key = f"{agent}:{a.session_id}"
    cursor = a.cursor if a.cursor is not None else (load_cursor(key) if key else "")
    if agent == "claude":
        result = fetch_claude(cursor, a.max_chars)
    else:
        result = fetch_deeptutor(cursor, a.max_chars, a.session_id)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
