---
description: Spawn an independent multi-agent review board over a PR or the current branch, gated on this repo's CLAUDE.md hard rules.
argument-hint: "[PR number | empty = current branch vs main] [--comment] [--fast]"
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git merge-base:*), Bash(git status:*), Bash(git show:*), Bash(gh pr diff:*), Bash(gh pr view:*), Bash(gh pr comment:*), Read, Grep, Glob, Agent
---

# Review board

You are the **chair** of a review board. You do **not** review the code yourself — you
assemble the diff, spawn a panel of **independent** reviewers (one concern each, no shared
context), adversarially verify what they find, and report a verdict. The board is tuned to
this repo's non-negotiables in [CLAUDE.md](../../CLAUDE.md) and [BRIEF.md](../../BRIEF.md).

Arguments: `$ARGUMENTS`
- A number → review that GitHub PR (`gh pr diff <n>`, `gh pr view <n>`).
- Empty → review the current branch vs `main` (`git diff $(git merge-base main HEAD)...HEAD`).
- `--comment` → after reporting, post the summary to the PR with `gh pr comment` (PR mode only). Never push or edit code.
- `--fast` → run 4 core members (determinism, leak-hygiene, honest-claims, correctness) instead of all 6.

## Step 1 — Assemble the materials (do this yourself, once)

1. Resolve the diff per the arguments above. If empty and `HEAD == main`, stop and say there is nothing to review.
2. Capture: the **full diff**, the list of **changed files**, and the **commit messages** in range (`git log --format='%H %s%n%b' main..HEAD` or `gh pr view`).
3. Read the **root `CLAUDE.md`** and any `CLAUDE.md` in modified directories — these are the binding rules. Quote the exact rule text into each reviewer's brief so findings can cite it.

## Step 2 — Convene the board (spawn in ONE message, in parallel)

Launch the members below as **separate `Agent` calls in a single message** so they run
concurrently and independently. Give each member: the diff, the changed-file list, the
relevant CLAUDE.md rule text, and the **shared output contract** (Step 3). Each member is
**read-only** (it may Read/Grep/Glob the repo for context but must not edit, commit, or push)
and is told: *"Review ONLY your assigned concern. Default to skepticism. A finding you cannot
tie to a specific line and a concrete consequence is not a finding."*

**Members (each independent):**

1. **Determinism & reproducibility.** Same `(seed, profile)` → byte-stable output. Hunt for: wall-clock reads (`date.today`, `now()`, `Date`, `time()`, `Math.random`, `Faker.date_of_birth`), unseeded RNG, dict/set ordering leaking into output, missing `sort_keys`, PDF/docx non-determinism (is `SOURCE_DATE_EPOCH` set? is the docx zip normalized + core dates pinned?), LLM content not cached by `(seed, doc_id)`. Rule: *"Determinism is non-negotiable … same seed → byte-stable corpus."*
2. **Leak hygiene / public-repo safety.** This is a public portfolio repo. Hunt for: real local filesystem paths, secrets/keys/tokens, real PII (vs. clearly-synthetic), references to unrelated private projects, internal hostnames. Rule: *"Public-repo hygiene … no real local filesystem paths, no references to unrelated private projects."*
3. **Honest claims (docs ↔ code).** Do README / BRIEF / docs / module tables describe only what is actually built? Are planned items marked planned? Did this diff change behavior without updating the matching doc, or claim a capability the code doesn't deliver? Rule: *"Honest. README/wiki/docs describe only what's built; mark planned items as planned."*
4. **Correctness & edge cases.** A focused bug scan of the changed lines only: logic errors, broken FK/joins, off-by-ones, unhandled empties (e.g. 0-endorsement / single-element-`rng.choice` paths), schema/manifest/golden inconsistencies, validation gaps. Ignore anything a linter/typechecker/CI would catch and anything on unmodified lines.
5. **Synthetic-data integrity.** Are synthetic markers present in metadata and on visible pages? Are IDs unmistakably fake (e.g. `9NN-NN-NNNN` tax ids)? Could any generated entity collide with a real person/company/policy? Rule: *"Synthetic only, clearly labeled."*
6. **Repo hygiene & commit discipline.** Is the heavy corpus gitignored (generator, not dump — only `generator/` + `sample/` + `golden/` committed)? Do commit messages **avoid AI co-author trailers** (CLAUDE.md: *"no AI co-author trailers"*)? Are large/binary artifacts committed that shouldn't be? Does `make validate` / the test contract still hold for what changed?

## Step 3 — Shared output contract (give verbatim to each member)

> Return ONLY a JSON array of findings (or `[]`). Each finding:
> `{"severity": "critical|high|medium|low", "file": "path", "lines": "L<start>-L<end>", "concern": "<your board concern>", "title": "<short>", "why": "<the concrete consequence>", "rule": "<exact CLAUDE.md/BRIEF text or null>", "fix": "<concrete suggested change>"}`.
> No prose outside the JSON. Omit anything you cannot tie to a specific changed line.

## Step 4 — Adversarial verification (kill false positives)

Collect all findings. For every **critical/high** finding, spawn **one independent verifier
`Agent`** whose job is to **refute** it: *"Here is a claimed issue. Try to show it is wrong,
a false positive, a pre-existing issue, or on an unmodified line. Return `{verdict: real|false_positive|uncertain, reason}`. Default to `false_positive` if you cannot confirm it."*
Drop findings the verifier marks `false_positive`. Verify medium/low only if cheap (skip under `--fast`).

## Step 5 — Report

Synthesize a single board report:
- A **verdict line**: `PASS` (no surviving critical/high) or `BLOCK` (≥1 surviving critical/high), with counts by severity.
- A findings **table**: severity · concern · `file:lines` · title · cited rule · suggested fix. Highest severity first. Dedupe overlapping findings across members.
- A one-line **per-member roll-call** (e.g. "Determinism: clean · Leak-hygiene: 1 high · …") so silent/empty members are visible, not assumed-clean.
- If `[]` across the board: state "No surviving findings" and what was checked.

You do not fix anything and you do not push or commit — the board only reports. If `--comment`
and reviewing a PR, post the report via `gh pr comment` (brief, no emojis), then stop.
