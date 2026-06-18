# X Engagement Agent

A local, file-based agent for founder-led X/Twitter engagement. It helps a human operator learn a persona's voice, find relevant posts, draft replies and original posts, review drafts, and capture post-send performance learnings.

The project is designed for public code and private data:

- `data/` is your real runtime state and is gitignored.
- `example/data/` is committed starter data showing the expected shape.
- The dashboard and agent modes read from `data_root` in `config/app.yaml`.

The agent is human-gated. It drafts and queues content; a human reviews every send.

## Quick Start

Prerequisites: Python 3.11+ and Node.js 20+.

```powershell
.\scripts\init-data.ps1
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
npm install
npm run build
.\.venv\Scripts\python dashboard/server.py
```

Open http://127.0.0.1:8787.

For frontend development, run the backend and Vite dev server in separate terminals:

```powershell
.\.venv\Scripts\python dashboard/server.py
npm run dev
```

Vite serves the React dashboard at http://127.0.0.1:5173 and proxies `/api` to the local FastAPI backend.

## Documentation

- [AGENTS.md](AGENTS.md): runtime behavior contract for `learn`, `scroll`, `compose`, `send`, and `review`.
- [dashboard/README.md](dashboard/README.md): dashboard surfaces, editable files, and current limitations.
- [docs/file-map.md](docs/file-map.md): what belongs in each public, config, private data, and example file.
- [docs/data-boundary.md](docs/data-boundary.md): what stays private in `data/` vs. what is safe to publish.
- [docs/operator-guide.md](docs/operator-guide.md): day-to-day operating checklist.

## Modes

- `learn`: study your own posts/replies/likes and seed style/profile data
- `scroll`: browse X and draft replies/quotes/thread replies
- `compose`: draft original posts
- `send`: review, edit, and send human-approved drafts
- `review`: capture metrics after sends and update learnings

## Data Policy

Never commit real runtime data. Keep real personas, profiles, drafts, metrics, incidents, style docs, company facts, and private writing guides under `data/`.

Use `example/data/` for safe templates and sanitized examples. It mirrors the private `data/` folder shape.
