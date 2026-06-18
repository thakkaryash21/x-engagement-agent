# Standalone X Engagement Agent Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate the Twitter/X engagement agent into a standalone publishable repository while keeping all real runtime data local-only and preserving functionality.

**Architecture:** The public repo contains agent prompts, dashboard code, docs, templates, and sanitized examples. The gitignored `data/` directory contains all private runtime state: personas, company facts, CSV data, drafts, learnings, style docs, and writing guides. `config/app.yaml` points the code to the active `data_root`.

**Tech Stack:** Markdown prompts, CSV/YAML file store, stdlib Python dashboard, PowerShell bootstrap commands, git.

---

### Task 1: Create Repository Boundary

**Files:** `.gitignore`, `README.md`, `docs/data-boundary.md`, `config/app.yaml`

- [x] Create standalone folder under `D:\cruit-univ\x-engagement-agent`.
- [x] Add `.gitignore` with `/data/` ignored before first commit.
- [x] Add `config/app.yaml` with `data_root`, `agent_command`, and `dashboard_port`.
- [x] Document the public/private data boundary.

### Task 2: Preserve Private Runtime Data

**Files:** `data/**`

- [x] Move real personas, CSVs, drafts, learnings, style docs, and writing guides into `data/`.
- [x] Keep the original data shape under the new data root so mode procedures and the dashboard retain equivalent behavior.
- [x] Add `data/company-facts.md` as the local factual-claims source.

### Task 3: Provide Public Examples

**Files:** `example/data/**`

- [x] Mirror the private `data/` structure in `example/data/`.
- [x] Commit schema-only CSVs and safe Markdown templates.
- [x] Include a small fake draft example for dashboard onboarding.

### Task 4: Rewrite Runtime Paths

**Files:** `AGENTS.md`, `modes/*.md`, `dashboard/server.py`, `dashboard/static/*`, docs

- [x] Replace source-repo-relative paths with data-root paths.
- [x] Update dashboard reads/writes to resolve through `config/app.yaml` and `DATA_ROOT`.
- [x] Replace hard-coded company fact references with `data/company-facts.md`.

### Task 5: Verify Before Publishing

**Files:** entire repo

- [ ] Run syntax checks for dashboard Python.
- [ ] Run sensitive-reference grep for source repo paths and private KB paths.
- [ ] Run `git status --short --ignored` and verify `data/` is ignored.
- [ ] Review the staged file list before first commit.

