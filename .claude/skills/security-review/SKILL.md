---
name: security-review
description: Security review cho thay đổi pending trên branch xsmb (project-local override)
---

Override skill `security-review` global cho xsmb. Điền checklist riêng (XSS trong template kết quả, validate ngày tháng, rate limit endpoint xem kết quả, …) khi cần.

Mặc định: dùng skill global `~/.claude/skills/security-review/SKILL.md`.
