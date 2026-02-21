.PHONY: install-dev install-core install-rag install-web test test-core test-law test-rag dev-api dev-web build-web clean

install-dev:
	pip install -e packages/core
	pip install -e packages/law
	pip install -e "cli[all]"
	pip install -e packages/api 2>/dev/null || true

install-core:
	pip install -e packages/core
	pip install -e cli

install-rag:
	pip install -e "packages/rag[all]"

install-web:
	cd apps/web && npm install

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

build-web:
	cd apps/web && npm run build

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
