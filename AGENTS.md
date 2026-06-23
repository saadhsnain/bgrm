# AGENTS.md

This project follows the global agent instructions unless this file says otherwise.

## Project Shape

- Python CLI project managed with `uv`.
- Main entrypoint: `remove_background.py`.
- Tests live in `tests/` and run with `uv run pytest`.

## Boundaries

- Keep this as a local reusable CLI unless the user asks for a GUI, API, or desktop app.
- Prefer deterministic Pillow/OpenCV tests; do not depend on remote services or model downloads in unit tests.
- Do not edit generated media or binary image assets character-by-character.
