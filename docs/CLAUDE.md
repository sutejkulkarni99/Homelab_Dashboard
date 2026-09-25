# Model Routing Reference

## Aliases

| Alias | Provider | Use for |
|---|---|---|
| `fast` | Groq gpt-oss-20b | Default. Q&A, file ops, quick tasks, chat |
| `coding` | Groq gpt-oss-120b | Code generation, refactors, scripts |
| `coding-long` | OpenRouter Qwen3.8-27B | Large-context code work, multi-file changes |
| `coding-cohere` | Cohere Command-A | Precise instruction-following, tight formats |
| `strong` | NVIDIA Nemotron Super 120B | Deep reasoning, design decisions, "why" questions |
| `ultra` | NVIDIA Nemotron Ultra 550B | Hardest problems only (slow, ~28s) |
| `critical` | Google Gemini Flash-Lite | RESERVED — manual only, high-importance tasks |

## Rules

- Default to `fast`. Escalate only when the task class needs it.
- `critical` is never auto-routed. Invoke with `/model critical` explicitly.
- For anything crossing session boundaries: work in `/mnt/HomeLab_Share/` or `~/Projects/`.
- Prefer standard library and portable solutions. Assume Linux (Fedora) unless told otherwise.
- When in doubt about model choice, use `fast` and let the user redirect.

## System Context Reference

Before any task involving **new services, ports, docker, systemd, firewall, networking, or storage**, read `~/system/context.md`. It is the source of truth for what runs where.

After successful deployment of any new service (confirmed by user), propose an update to `~/system/context.md`:
- Add the new service to the appropriate section
- Add the port to Listening Ports (via snapshot)
- Add a Change Log entry
- Bump "Last updated"
Show the proposed diff. Do NOT write until user approves.
