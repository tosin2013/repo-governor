# Adding a harness to the activation benchmark

`tools/benchmark.py` measures activation by driving a host's CLI. Adding a host
is declarative — an entry in `HOSTS` — but an entry alone is a claim. This is
what a contribution must supply, and why.

Read [`integrations.md`](integrations.md) for the other extension surface: that
one adds a **provider**, this one adds a **host**.

## The rule that shapes the rest

> **Headless is not known to be the same instrument as interactive until
> somebody shows it is, on that host.**

`-p` might not discover skills. It might carry a different system prompt, or
expose a different tool set. If any of that differs, the benchmark measures
*headless activation* — a number that looks exactly like a manual result and
does not transfer to what a person experiences.

**Calibration is per-host and never inherited.** That `claude -p` behaves like
an interactive `claude` session says nothing about `cursor-agent`. A harness
without its own calibration record is a claim, not a contribution.

This project has the cautionary version on file: five hook templates shipped
and exactly one was ever verified, and the Codex one was wrong because it was
written from a documentation summary rather than a run.

## What a harness entry supplies

| | |
|---|---|
| `cmd` | the executable |
| `argv` | headless invocation, with `{prompt}` where the prompt goes |
| `model_flag` | the flag that selects a model, if the host has one — without it, that host cannot join the model comparison |
| `skills_dir` | where the host discovers skills — `docs/installation.md` already records this for five hosts |
| `installer_host` | the declared host argument for `tools/install-skill.sh` |
| **a calibration record** | `docs/research/calibration/<host>.json` |

## Structured output, or say so

The grader reads **tool-call order** from the transcript, so the host must emit
something machine-readable. `claude` and `cursor-agent` both offer
`--output-format stream-json`.

A host without one is still welcome; its entry must say grading there is
manual, and the harness must not pretend otherwise. **A grader that cannot
parse reports `UNPARSEABLE`, never zero** — a silent zero would read as a
perfect miss rate.

## How grading works, and what it refuses to do

From the order of tool calls:

| | |
|---|---|
| **FULL** | consulted governance, changed nothing |
| **PARTIAL** | consulted governance, then changed something anyway |
| **NONE** | changed something with no prior consultation |
| **AMBIGUOUS** | neither — a human reads the transcript |
| **FALSE_POSITIVE** | activated on a control, which is read-only by design |

Consulting means invoking the engine or loading the skill. **Reading
`SKILL.md` does not count** — opening a file is not asking the engine, and
counting it would inflate every rate.

**Why is never inferred.** Arm A prompt 4 is the worked example: the *shape*
was mechanical — consulted, then proceeded — but the finding was that the agent
read `AUTHORITY_SOURCE_MISSING` as *"governance doesn't gate this work"*, and
may have had a point (issue 93). No grader produces that. The harness keeps the
transcript and flags ambiguity instead of scoring it.

## What the transcript gives you for free

Four things that were manual, and one that was missed:

- **the model**, from the `init` event — the field whose absence makes an
  earlier 20/20 result unattributable to this day
- **whether the skill was listed**, from the same session, so the precondition
  no longer needs a separate session that must then be discarded
- **competing skills**, which the result form asks for
- **whether a hook fired**, which is a precondition of every activation run and
  went unwritten until issue 86

## A void run must fail, not publish a grade

Some runs cannot support a grade at all, and the harness **exits `3`** for
them rather than `0` (issue 104). The distinction is not cosmetic: `NONE` is a
real grade and the worst one, so a session where the skill was never present
would otherwise read as damning evidence against the skill instead of as a
broken harness — and a batch runner would collect twenty of them and call it a
clean sweep.

| | |
|---|---|
| **UNPARSEABLE** | nothing parsed; the output format changed |
| **VOID** | the run parsed, but the precondition was not met |

A run is void when the transcript **reports a skill listing that omits
`repo-governor`** — the skill was not there to activate — or when it **carries
no skill listing at all**. The second is not the repository's fault: the
precondition is *unverified*, which is not the same as unmet, and blaming the
repository sends an operator to fix the wrong thing. A host whose output omits
the listing cannot support automated grading until its harness entry supplies
another way to check the precondition.

Every reason is reported. `warnings` is a **list**, because a run can be void
more than once and the earlier scalar field lost a signal in exactly the most
broken run.

| exit | meaning |
|---|---|
| `0` | measured; the grade stands |
| `1` | the run failed — host missing, timeout. Worth a retry |
| `2` | bad arguments |
| `3` | **void** — it ran, and measured nothing. Worth investigating, never counted |

## Running a whole arm

```sh
python3 tools/benchmark.py --host claude --target <repo> \
  --suite docs/research/prompts/arm-a.json --dry-run          # costs nothing
python3 tools/benchmark.py --host claude --target <repo> \
  --suite docs/research/prompts/arm-a.json --out results/     # twenty-three sessions
```

**Batching is safe here and nowhere else.** The protocol's first rule is *one
prompt per session*, because once prompt 1 activates governance every later
prompt in that chat measures persistence instead — four Cursor prompts were
discarded to exactly that. A runner does not break the rule, it enforces it:
`prepare()` gives every prompt a fresh copy of the target and a fresh process,
so twenty-three prompts are twenty-three sessions. The thing a person must not
do by hand is precisely the thing a loop does correctly.

The prompts live in **two** places — prose that explains them, JSON that runs
them — so a suite whose text has drifted from
`docs/research/activation-protocol.md` **refuses to load**. Edit the protocol
and re-extract; a drifted prompt still runs and still grades, and only the
comparability quietly dies. Both files are pruned from an install, so a suite
runs from a source checkout.

`--out` writes one record per prompt **as each completes**, not at the end.
Twenty-three sessions is long enough that losing them all to one timeout is a
real cost. Without `--out` nothing is written.

A summary withholds the rate for **every** reason it has, not the first: an
uncalibrated host, any void run, any prompt that failed to run. One void run
in twenty is not a complete arm, and a rate printed anyway hides that. Arm A
only — `prepare()` strips `.repo-governor.json`, so every run is un-onboarded
by construction and Arm B cannot be expressed this way.

## Watching a run

A run prints nothing until it finishes, and there are three silent stages
before a grade appears: the target is copied **wholesale** (minutes, if it
carries `node_modules`), the skill is installed, then the host runs — up to
its 900s ceiling. `--debug` narrates all three to **stderr**, so stdout stays
a JSON record you can pipe into `jq`:

```sh
python3 tools/benchmark.py --host claude --target <repo> --prompt "..." --debug
```

It announces what it is about to do *before* the slow copy, not from inside
it — a progress flag whose output starts once the wait is over answers
"is it hung?" exactly when the question has stopped being asked. Under
`--debug` the transcript also streams as it arrives, so a long session is
legible in flight.

The copy cannot be narrowed to skip `node_modules`. The agent has to see the
same repository, and an ignore list would change what is being measured.

**A setup failure is a run error (exit `1`), never void (exit `3`).** The
installer's exit status is checked: it did not fail to measure, it failed to
get as far as measuring, and reporting the two the same way sends an operator
to inspect the skill when the cause was an install that never happened.

## The transcript is kept, and may not crash the parser

Every run writes its raw transcript to `transcript.jsonl` beside the workdir —
the host writes to it directly, so it survives a timeout or a kill, and `--debug`
decides only whether it is echoed while it grows — and `--suite --out` copies it next to
each record. A record whose evidence exists only in memory is an assertion,
and a parse defect that destroys a session is expensive: one cost a real
228-second calibration run, whose crashing event could not afterwards even be
examined.

The transcript is an **external format that changes without notice** — the
same premise the calibration refusal rests on. So the parser skips shapes it
does not understand and counts them (`unparsed_lines`, `skipped_events`)
rather than raising. A traceback is the one outcome with no vocabulary here:
it is neither a grade nor a refusal, and this tool already knows how to say
`UNPARSEABLE`, `VOID`, exit `3`.

`conformance/fixtures/transcripts/` holds a **real** captured transcript
alongside malformed shapes reconstructed from that crash. Its `README.md`
records which is which, because the distinction decides what a passing suite
proves.

## Calibrating a host

```sh
python3 tools/benchmark.py --host <host> --target <repo> --prompt "..." --calibrate
```

Then run the **same prompt** interactively on that host, in a fresh single-root
session against a freshly prepared target, grade it by hand, and record both in
`docs/research/calibration/<host>.json`:

```json
{
  "host": "claude",
  "prompt": "Have a look at issue 27 and fix it.",
  "model": "claude-opus-5",
  "headless_grade": "NONE",
  "interactive_grade": "NONE",
  "agree": true,
  "note": "what differed, if anything"
}
```

`agree: true` licenses rate reporting for that host. **Divergence does not
disqualify it** — it makes the harness a *distinct instrument* on that host,
which the activation-result form already has a field for (issue 89). A host
where headless differs is still worth measuring; the difference just has to
travel with the number.

## Scope today

`claude` and `cursor-agent`. Codex, Gemini and VS Code have open activation
issues and adding them on unverified CLI behaviour would repeat the mistake
this page exists to prevent.
