# Data Boundary

`data/` is the private runtime boundary. It contains everything learned, personal, company-specific, or operational.

Committed code should use `config/app.yaml` to find `data_root`; it should not hard-code personal paths or source repo paths.

## Runtime Config

- `config/app.yaml`: non-sensitive app wiring (`data_root`, dashboard port, agent command)
- `config/limits.yaml`: operating limits and pacing defaults
- `config/metrics.yaml`: metrics capture and optimization defaults

These files are part of the public repo. Keep broadly reusable defaults here. Put private persona data, company facts, drafts, CSV rows, writing guides, and learned style under `data/`.

## Private Runtime Data

- `data/personas/`: real persona definitions
- `data/company-facts.md`: verified company facts for factual claims
- `data/csv/`: CSV database
- `data/drafts/`: draft queue and archives
- `data/learnings/`: review-mode learnings
- `data/style/`: learned persona style docs
- `data/writing/`: private writing and voice guides

## Public Examples

`example/data/` mirrors the private data structure with safe templates and schema-only CSVs. New users can copy it to `data/` to initialize a private workspace. Config defaults already live in `config/`.

## Dashboard Editing Boundary

The dashboard edits canonical local files directly:

- Draft decisions update `data/drafts/` and rows in `data/csv/*.csv`.
- Settings update `config/*.yaml` and active persona state.
- Knowledge edits Markdown under `data/personas/`, `guidelines/`, `data/style/`, `data/writing/`, and `data/learnings/`.

Before publishing, run `git status --short --ignored` and `git ls-files 'data/*'` to verify real runtime data remains untracked.


