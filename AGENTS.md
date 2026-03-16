# Repository Guidelines

## Project Structure & Module Organization
This repository is a Python and TypeScript monorepo. Backend packages live under `packages/`: `core` contains the crawler engine, `law` adds law-specific scrapers, `rag` handles PDF ingestion and retrieval, and `api` exposes the FastAPI service. Frontend apps live in `apps/`: `web` is the Vite admin UI and `lawchat` is the Next.js chat interface. The CLI entry point is in `cli/src/autocrawler_cli/`. Tests live in `packages/*/tests`. Ops scripts and container assets live in `scripts/` and `docker/`.

## Build, Test, and Development Commands
Use the top-level `Makefile` for common workflows:

- `make install-dev`: install editable backend packages and CLI.
- `make install-rag`: install the RAG package with optional providers.
- `make install-web` / `make install-lawchat`: install frontend dependencies.
- `make dev`: run API on `:8000`, Vite admin UI, and Next.js law chat together.
- `make dev-api`, `make dev-web`, `make dev-lawchat`: run one service locally.
- `make build-web` / `make build-lawchat`: create production frontend builds.
- `make test`: run core, law, and RAG test suites.
- `pytest packages/api/tests -v`: run API tests, which are not included in `make test`.

## Coding Style & Naming Conventions
Python uses 4-space indentation, type hints where practical, and `snake_case` for modules, functions, and test names. TypeScript and React files use 2-space indentation, `PascalCase` for components such as `PDFUpload.tsx`, and `camelCase` for hooks and helpers. Keep package code under `src/`. No dedicated formatter or linter is configured today, so match the surrounding file style and keep imports ordered consistently.

## Testing Guidelines
The backend test stack is `pytest`; API route tests also use `fastapi.testclient`. Add tests under the corresponding `packages/*/tests` directory and name files `test_<feature>.py`. Prefer narrow unit tests for crawler logic, provider configuration, and route behavior. Run the relevant package tests before opening a PR, including API tests when touching `packages/api`.

## Commit & Pull Request Guidelines
Recent history follows short Conventional Commit subjects such as `feat: add lawrag sync CLI subcommand` and `fix: rename webhook secret to WEBHOOK_SECRET`. Keep subjects imperative and scoped to one change. PRs should include a concise summary, linked issue when relevant, test coverage notes, and screenshots for UI changes in `apps/web` or `apps/lawchat`.

## Configuration & Security
Required local secrets are passed by environment variables, including `VOYAGE_API_KEY` and `ANTHROPIC_API_KEY`. Keep secrets in local `.env` files and never commit generated data or credentials. When testing webhook flows, verify secret names against current config before merging.
