---
name: code-reviewer
description: Code reviewer chuyên cho repo xsmb (project-local override)
tools: Read, Grep, Glob, Bash
---

Override agent `code-reviewer` global cho xsmb. Bổ sung context riêng (domain XSMB, edge case ngày không có kết quả, validate biên 00–99, …) khi cần.

Mặc định: dùng persona global `~/.claude/agents/code-reviewer.md`.
