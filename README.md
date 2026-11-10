# study-notes

学习笔记 skill（SKILL.md 格式，跨 agent 通用）：把当前对话新学的内容按
**康奈尔笔记法 + 费曼技巧**整理进 Obsidian 多文件知识库（index 索引 + 主题文件）。

## 功能

- **增量记笔记**：只处理当前会话两次调用之间的新消息（游标管理，不重复、不回填）
- **智能落位**：读完整索引与相关主题文件后判断——归属已有章节则补充/修正；
  无归属则新开主题文件并按知识前后关系插入索引合适位置（不默认文末）
- **修正优先于追加**：新内容推翻旧表述时直接改写，不并存
- **拆解导入**：旧笔记（本地文件 / 粘贴文本 / 飞书文档 URL）拆解入库，重叠自动合并去重
- **每周全量审查**：检查矛盾 / 冗余 / 顺序 / 三栏劣化；结构性改动先列方案确认

## 笔记格式（每个知识点一块）

- 🧵 线索栏：讲什么 + 关键问题（自测用）
- 📖 主栏：核心概念 / 要点 / 例子 / 易错点（写修正后的版本）
- 💡 总结栏：费曼式一句话白话解释（只记最终正确版，不记中间尝试）

## 安装

需要 Python 3.10+（仅标准库）。

```bash
# Claude Code
git clone https://github.com/LIU111227/study-notes ~/.claude/skills/study-notes

# DeepTutor（workspace 的 skills 目录）
git clone https://github.com/LIU111227/study-notes <deeptutor-workspace>/skills/study-notes
```

首次使用会引导配置 vault 路径与学科目录（存于 `~/.config/study-notes/config.json`）。

## 使用

对话里说"记笔记 / 整理笔记 / 拆解笔记入库：… / 审查笔记"即可触发。

## 适配的宿主 agent

- DeepTutor（读本地 API 会话）
- Claude Code（读 transcript jsonl）

fetcher 为插件式设计，可自行扩展其他 agent 的对话源适配。
