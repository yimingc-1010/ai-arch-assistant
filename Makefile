.PHONY: install-dev install-rag test test-core test-law test-rag dev-api dev-web clean

install-dev:
	pip install -e packages/shared
	pip install -e packages/core
	pip install -e packages/law
	pip install -e "cli[all]"
	pip install -e packages/db 2>/dev/null || true
	pip install -e packages/api 2>/dev/null || true
	pip install -e packages/scheduler 2>/dev/null || true

install-core:
	pip install -e packages/shared
	pip install -e packages/core
	pip install -e cli

install-rag:
	pip install -e "packages/rag[all]"

test: test-core test-law test-rag

test-core:
	pytest packages/core/tests -v

test-law:
	pytest packages/law/tests -v

test-rag:
	pytest packages/rag/tests -v

dev-api:
	uvicorn autocrawler_api.app:app --reload --port 8000

dev-web:
	cd apps/web && npm run dev

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
