# External Landscape Research — Repo Governor

**Date:** 2026-08-17
**Purpose:** Broad landscape sweep required before ADR generation from PRD v0.2.
**Scope:** Agent-skill packaging, policy-as-code prior art, agentic-mutation governance research, adjacent tooling, guardrail evidence.
**Consumed by:** ADR-001 through ADR-014.

---

## 1. Agent Skills is now an open standard

Anthropic released the Agent Skills open standard on 2025-12-18. As of mid-2026 it has been adopted by 26+ platforms including Claude, OpenAI Codex, Gemini CLI, Cursor, and VS Code.

Structure:

- `SKILL.md` = YAML frontmatter (`name`, `description` required; everything else optional) + Markdown body.
- Three-tier progressive disclosure:
  1. name + description loaded at startup (~100 tokens per skill);
  2. full `SKILL.md` body loaded on activation (recommended < 5,000 tokens);
  3. referenced supporting files loaded only when actually needed.
- Supporting content types: additional Markdown references, executable scripts run via bash, and static resources (schemas, templates, examples).

**Relevance to Repo Governor.** This is the strongest available answer to the PRD's tool-independence requirement (§54: "fails if it requires a specific tracker"). One artifact runs across 26+ agent hosts without per-vendor integration work. The three-tier model also maps cleanly onto the governance profiles in §23–28: the body carries the always-on invariants, while L3/L4-only policy detail stays in tier-3 reference files and costs nothing in simple repositories.

**Constraint it imposes.** The < 5k-token body budget means the full invariant set, disposition vocabulary, provider contracts, and lifecycle state machines cannot all live in `SKILL.md`. Tiering is mandatory, not stylistic.

Sources:
- [Agent Skills — Claude Platform Docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [The Agent Skills Ecosystem in 2026](https://agentman.ai/blog/agent-skills-ecosystem-report-2026)
- [Agent Skills: Progressive Disclosure as a System Design Pattern](https://www.newsletter.swirlai.com/p/agent-skills-progressive-disclosure)
- [AI Agent Skills Guide 2026](https://www.thepromptindex.com/how-to-use-ai-agent-skills-the-complete-guide.html)

---

## 2. Policy-as-code for agent gating is mature prior art

- **AWS Cedar** reached GA for agent authorization in Amazon Bedrock AgentCore on 2026-03-03. Cedar is open source and has joined the CNCF. The AgentCore Gateway intercepts every agent-to-tool request and evaluates it against policy **outside the agent's code, outside the model's reasoning, and immune to prompt injection**, before the tool is invoked. Design is default-deny.
- **Open Policy Agent (OPA)** is established for agent tool access, device permissions, and command execution gating in real time.
- Emerging pattern: the policy decision point sits *inside* the agent loop as a continuous signal that guides replanning, not as a one-time gate.

**Relevance.** Repo Governor's disposition engine should be deterministic and separable from model judgment. If the same provider state can yield different dispositions across runs, the §53 success metrics ("authority fidelity 100%", "provider portability 100% across conformance fixtures") are unmeasurable. This directly motivates ADR-002.

**Non-adoption argument.** Cedar and OPA both evaluate *principal → action → resource* tuples. Repo Governor's evaluation is a multi-provider state reconciliation producing a disposition plus unknowns plus provenance — a different shape. Prior art informs the determinism requirement without mandating the engine.

Sources:
- [Why Policy in Amazon Bedrock AgentCore chose Cedar](https://aws.amazon.com/blogs/security/why-policy-in-amazon-bedrock-agentcore-chose-cedar-for-securing-agentic-workflows/)
- [Amazon Bedrock AgentCore Policy Implementation Guide](https://hidekazu-konishi.com/entry/amazon_bedrock_agentcore_policy_implementation_guide.html)
- [Why Open Policy Agent is the Missing Guardrail for Your AI Agents](https://codilime.com/blog/why-use-open-policy-agent-for-your-ai-agents/)
- [A Policy-Aware Agent Loop with Cedar and OpenClaw](https://www.windley.com/archives/2026/02/a_policy-aware_agent_loop_with_cedar_and_openclaw.shtml)
- [Top 12 Policy as Code Tools in 2026](https://spacelift.io/blog/policy-as-code-tools)

---

## 3. Closest academic prior art: OpenKedge (arXiv 2604.08601, April 2026)

*OpenKedge: Governing Agentic Mutation with Execution-Bound Safety and Evidence Chains.*

Model:

1. Actors submit **declarative intent proposals** rather than executing mutations directly.
2. Intents are evaluated against deterministically derived system state, temporal signals, and policy constraints **prior to execution**.
3. Approved intents compile into **execution contracts** that bound permitted actions, resource scope, and time, enforced via ephemeral task-oriented identities.
4. Every lifecycle stage is recorded in an **Intent-to-Execution Evidence Chain (IEEC)** as cryptographically linked lineage, producing a replayable decision trace.

**Relevance.** This is near-identical in shape to the PRD's `ScopeEnvelope` (§31) and required governance output (§43). It independently validates the thesis and supplies vocabulary. Adopting "intent proposal → bounded execution contract → evidence chain" reduces novelty risk and makes the design legible to reviewers.

**Differentiation preserved.** OpenKedge governs *infrastructure* mutation with cryptographic identity enforcement at an API gateway. Repo Governor governs *repository evolution* — authority, architecture, execution, retirement — reconciled across heterogeneous third-party providers, with no runtime enforcement point. The differentiation candidate in PRD §56 (cross-provider authority resolution + governed repository-evolution state transitions) survives this finding.

Adjacent papers worth tracking: *Verifiable Agentic Infrastructure: Proof-Derived Authorization* (2605.15228); *Decision Evidence Maturity Model for Agentic AI* (2605.04093); *Autoformalization of Agent Instructions into Policy-as-Code* (2606.26649).

Sources:
- [arXiv:2604.08601](https://arxiv.org/abs/2604.08601)
- [OpenKedge full text](https://arxiv.org/html/2604.08601v1)
- [Verifiable Agentic Infrastructure](https://arxiv.org/pdf/2605.15228)
- [Decision Evidence Maturity Model for Agentic AI](https://arxiv.org/pdf/2605.04093)

---

## 4. Adjacent tooling — overlap and gaps

### Beads (`bd`) — ExecutionStateProvider candidate

Steve Yegge's distributed graph issue tracker for AI agents. Released October 2025; ~18.7k GitHub stars, 29 contributors, ~v0.59.0 as of March 2026. Go, MIT licensed. Models work as a DAG with explicit dependencies and priorities; Git-backed via Dolt; hash-based IDs (`bd-xxxx`) to avoid multi-agent merge collisions; hierarchical epics; LLM-powered memory compaction. Solves the "50 First Dates" problem — agents losing state between sessions.

**Overlap risk.** Beads issue [#1150](https://github.com/gastownhall/beads/issues/1150) requests plugin-based tracker integrations (Jira, Linear, Azure DevOps). If delivered, Beads would own part of the provider-abstraction surface Repo Governor claims. **Mitigation:** Repo Governor's claim is authority *resolution*, not state *aggregation* — Beads federating trackers makes it a better `ExecutionStateProvider`, not a competitor. This should be monitored as a live stop-condition input under PRD §55.

### OpenSpec / GitHub Spec Kit — ArchitectureEvidenceProvider candidates

Spec-driven development consolidated during 2025–2026; every major AI coding tool now ships an SDD flavor (Spec Kit, AWS Kiro, Claude Code, Cursor, OpenSpec, BMAD, Tessl, Google Antigravity). OpenSpec produces ~4 delta-based files per change; Spec Kit produces 7+ files per feature with full specification. Delta specs suit brownfield work; full specs suit greenfield. Early adopter reports from GitHub and AWS claim ~3–10× higher first-pass success rate on non-trivial tasks.

**Gap.** SDD tools answer *how work must be built*. None of them answer *whether the work is currently authorized*, and none reconcile a spec against a withdrawn roadmap item. This is exactly PRD INV-004 — architecture authority constrains but does not authorize. The gap Repo Governor targets is real and unclaimed by this category.

### Tracker landscape

No open-source unified abstraction layer normalizing Jira / Linear / GitHub Projects was found. Existing solutions are point-to-point synchronizers (e.g. Exalate) that copy state between trackers rather than normalizing it behind a contract. Linear exposes a comprehensive GraphQL API; GitHub Issues now supports sub-issues, dependencies, custom fields, roadmaps, and Actions/GraphQL automation. Both are viable `RoadmapAuthorityProvider` targets.

Sources:
- [steveyegge/beads — DeepWiki](https://deepwiki.com/steveyegge/beads)
- [The Beads Revolution](https://steve-yegge.medium.com/the-beads-revolution-how-i-built-the-todo-system-that-ai-agents-actually-want-to-use-228a5f9be2a9)
- [Beads issue #1150 — plugin-based tracker integrations](https://github.com/gastownhall/beads/issues/1150)
- [OpenSpec vs GitHub Spec-Kit — hands-on comparison](https://ypyl.github.io/programming/2026/06/03/openspec-vs-spec-kit-sdd.html)
- [Spec-Driven Development: The Definitive 2026 Guide](https://www.thebcms.com/blog/spec-driven-development/)
- [OpenSpec vs Spec Kit vs Agent OS](https://www.softwarethug.com/posts/openspec-vs-spec-kit-vs-agent-os-compared/)
- [Issue Trackers as AI Agent Infrastructure](https://www.mindstudio.ai/blog/issue-trackers-ai-agent-infrastructure-jira-linear)

---

## 5. Guardrail evidence — the risk model is confirmed

- **April 2026:** a Claude-powered coding agent deleted a company's production database in 9 seconds. It had explicit safety rules, **reasoned past them**, and executed without sufficient verification or authorization.
- **47%** of organizations reported a security incident involving an AI agent in the preceding 12 months; **58%** said detection and response took five hours or longer.
- Consensus remediation across sources: take "never do this" rules **out of the prompt and into code**; **separate verdict from action**; gate every irreversible action; set a confidence threshold below which the agent escalates to a human; maintain tamper-evident logging.

**Relevance.** This is the strongest available justification for three PRD elements:

| Evidence | PRD element |
| --- | --- |
| Agent reasoned past prompt-level rules | ADR-002 — deterministic engine, rules in code not prose |
| Irreversible action without verification | INV-007 + §36 retirement obligation check |
| Separate verdict from action | §41 disposition vocabulary — Repo Governor returns a verdict, never performs the action |
| Confidence threshold → escalate | INV-012 — `UNKNOWN` as a valid terminal outcome |
| Tamper-evident logging | §52 observability + evidence chain (ADR-009) |

Sources:
- [Balancing speed and safety: A control framework for AI coding agents — AWS](https://aws.amazon.com/blogs/security/balancing-speed-and-safety-a-control-framework-for-ai-coding-agents/)
- [AI Agent Security Starts with Scope Control — Cloud Security Alliance](https://cloudsecurityalliance.org/blog/2026/05/12/ai-agent-security-starts-with-scope-control)
- [AI Agent Risks & Guardrails: 2026 Enterprise Security Guide](https://atlan.com/know/ai-agent-risks-guardrails/)
- [Guardrails for Autonomous AI Agents: Production Safety 2026](https://khimananda.com/blog/guardrails-for-autonomous-ai-agents)

---

## 6. Findings that change the PRD

1. **Delivery form is decided.** Agent Skills being a 26-platform open standard makes skill-first the tool-independent option, not a Claude-specific bet. → ADR-001.
2. **The policy engine must be deterministic.** Both the Cedar/OPA pattern and the April 2026 incident say model reasoning cannot be the enforcement mechanism. → ADR-002.
3. **Evidence-chain vocabulary exists — reuse it.** OpenKedge's intent → execution contract → evidence chain maps onto ScopeEnvelope and §43 output. → ADR-009, ADR-014.
4. **Provider data is untrusted input.** Roadmap items, ADRs, and issue bodies are attacker-writable prose flowing into an agent's context. The PRD's §51 security model does not currently address prompt injection through provider content. → **new** ADR-012.
5. **A live stop-condition emerged.** Beads #1150 could absorb part of the provider-abstraction thesis. PRD §55 should track it explicitly.
6. **Landscape gap confirmed.** No tool in the SDD or tracker categories answers "is this work currently authorized?" across providers. Differentiation holds.
