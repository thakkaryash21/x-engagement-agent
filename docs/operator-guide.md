# Operator Guide

1. Copy `example/data` to `data`.
2. Fill in `data/personas/`, `data/company-facts.md`, and `data/writing/`.
3. Create a virtual environment with `python -m venv .venv`.
4. Install dependencies with `.\.venv\Scripts\python -m pip install -r requirements.txt` and `npm install`.
5. Build the web app with `npm run build`.
6. Start the dashboard with `.\.venv\Scripts\python dashboard/server.py`.
7. Open http://127.0.0.1:8787.
8. Use the Knowledge tab for persona, guideline, style, writing, and learning Markdown edits.
9. Use Settings for limits, metrics, active persona, and tagging defaults.
10. Run `learn` before `scroll`, `compose`, or `send` so the style doc has confirmed patterns.
11. Keep one browser session and one agent session active at a time.
12. Stop immediately if X shows a challenge, suspicious-login warning, logged-out state, or unexpected UI breakage.


