# Repository Guidelines

## Project Structure & Module Organization
- `src/sentinel/` holds the application package (CLI entrypoint is `sentinel.cli:main`).
- `tests/` contains unit tests; `tests/integration/` contains API-keyed integration tests.
- `docs/` holds architecture and system design references.
- `data/` is the runtime state directory (persona files like `data/identity.md` and `data/agenda.md`).
- Root configs include `pyproject.toml`, `.env.example`, and `uv.lock`.

## Build, Test, and Development Commands
- `uv sync` installs dependencies into the local environment.
- `uv run sentinel --help` verifies the CLI is wired up.
- `uv run sentinel init` initializes `data/` and persona files.
- `uv run sentinel run` starts the Telegram bot; add `--debug` for log output.
- `uv run pytest -v` runs the test suite (integration tests are ignored by default).
- `uv run pytest tests/integration -v` runs integration tests (requires `.env` with API keys).
- `uv run ruff check src tests --fix` lints and auto-fixes issues.

## Coding Style & Naming Conventions
- Python 3.12+ only; prefer clear, terse code with self-explanatory structure.
- Line length: 100 characters (`ruff` enforces this).
- Follow `ruff` lint rules (`E`, `F`, `I`, `UP`, `B`, `SIM`).
- Keep modules consolidated; add new files only for clear separation of concerns.

## Testing Guidelines
- Primary framework: `pytest` with `pytest-asyncio`.
- Integration tests live under `tests/integration/` and require real API keys.
- Test names should be descriptive and map to functionality (e.g., `test_llm_routing.py`).

## Commit & Pull Request Guidelines
- Use Conventional Commits observed in history (e.g., `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`).
- Keep commits scoped to one change set and include context in the message.
- PRs should include: clear description, linked issue (if any), and test results.
- If behavior changes, add or update tests and note how to validate locally.

## Security & Configuration Tips
- Do not commit `.env` or secrets; use `.env.example` for reference.
- Integration tests require provider keys such as `SENTINEL_ANTHROPIC_API_KEY`.
- Treat `data/` as local state; avoid committing generated runtime files.
