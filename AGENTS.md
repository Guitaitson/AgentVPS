# Repository Guidelines

## Project Structure & Module Organization
Core application code lives in `core/`, split by concern: orchestration in `core/vps_agent/` and `core/vps_langgraph/`, builtin skills in `core/skills/_builtin/`, integrations in `core/integrations/`, and autonomous/update flows in `core/autonomous/` and `core/updater/`. The Telegram entrypoint is `telegram_bot/bot.py`. Configuration, migrations, compose files, and service units live in `configs/`. Tests are in `tests/`. Operational and architecture notes belong in `docs/`. Windows-side voice tooling lives in `desktop_companion/windows/`.

## Build, Test, and Development Commands
- `pip install -e ".[dev]"`: install the project plus lint/test tooling.
- `pip install -e ".[voice]"`: add local voice transcription dependencies.
- `python -m pytest -q`: run the full test suite.
- `python -m pytest tests/test_voice_context.py -q`: run a focused test slice.
- `python -m ruff check .`: lint the repository.
- `python -m ruff format --check .`: verify formatting.
- `python -m telegram_bot.bot`: run the Telegram bot locally.
- `python -m core.mcp_server`: run the MCP server locally.

## Coding Style & Naming Conventions
Use Python 3.11+ compatible code and follow Ruff defaults configured in `pyproject.toml` (`line-length = 100`). Use `snake_case` for modules, functions, variables, and tests; `PascalCase` for classes. Keep builtin skills under `core/skills/_builtin/<skill_name>/` with `handler.py` and `config.yaml`. Prefer small, explicit helpers over large mixed-responsibility functions.

## Testing Guidelines
The project uses `pytest` and `pytest-asyncio`. Coverage is enforced with a floor of `60%`. Name tests `tests/test_*.py` and keep new tests close to the behavior changed. For integration-heavy changes, run focused suites first, then `python -m pytest -q` before opening a PR.

## Commit & Pull Request Guidelines
Follow the existing Conventional Commit pattern: `feat(...)`, `fix(...)`, `docs(...)`, `ci(...)`. Keep PRs scoped to one concern, branch from `main`, and merge only after green CI. Include a short summary, risk/impact, and the validation commands you ran. Production changes ship via GitHub Release; do not treat temporary branches as deploy targets.

## Security & Operations
Never commit real secrets. Use `configs/.env.example` as the template and keep runtime credentials in environment files only. When touching external specialists such as FleetIntel or BrazilCNPJ, preserve the boundary: AgentVPS handles routing, auth, UX, memory, and fallback; the external system owns domain logic and specialist output.
