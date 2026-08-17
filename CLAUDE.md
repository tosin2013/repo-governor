See [AGENTS.md](AGENTS.md).

Repo Governor is tool-independent by thesis ([ADR-001](docs/adrs/001-agent-skill-as-primary-delivery-surface.md)), so its own agent instructions live in the cross-vendor file rather than a Claude-specific one. This file exists only so Claude Code loads them; keeping the content here instead would be a vendor bet in a project whose §54 failure conditions warn against exactly that.
