# Data Boundary

`data/` is the private runtime boundary. It contains everything learned, personal, company-specific, or operational.

Committed code should use `config/app.yaml` to find `data_root`; it should not hard-code personal paths or source repo paths.

## Private Runtime Data

- `data/personas/`: real persona definitions
- `data/company-facts.md`: verified company facts for factual claims
- `data/config/`: operator limits and metrics targets
- `data/data/`: CSV database
- `data/drafts/`: draft queue and archives
- `data/learnings/`: review-mode learnings
- `data/style/`: learned persona style docs
- `data/writing/`: private writing and voice guides

## Public Examples

`example/data/` mirrors the private structure with safe templates and schema-only CSVs. New users can copy it to `data/` to initialize a private workspace.

## Dashboard Editing Boundary

The dashboard may edit local private data, but those edits still land in files under `data/` or in public playbooks under `guidelines/`:

- Draft decisions update `data/drafts/` and rows in `data/data/*.csv`.
- Settings update `data/config/*.yaml` and active persona state.
- Knowledge edits Markdown under `data/personas/`, `guidelines/`, `data/style/`, `data/writing/`, and `data/learnings/`.

Before publishing, run `git status --short --ignored` and `git ls-files 'data/*'` to verify real runtime data remains untracked.


