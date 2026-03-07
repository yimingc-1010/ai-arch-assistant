.PHONY: install-dev install-core install-rag install-web install-lawchat test test-core test-law test-rag dev dev-api dev-web build-web dev-lawchat build-lawchat dev-backend dev-frontend docker-ingest docker-ingest-all clean

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

install-lawchat:
	cd apps/lawchat && npm install

test: test-core test-law test-rag

test-core:
	pytest packages/core/tests -v

test-law:
	pytest packages/law/tests -v

test-rag:
	pytest packages/rag/tests -v

dev:
	@trap 'kill 0' INT; \
	uvicorn autocrawler_api.app:app --reload --port 8000 & \
	(cd apps/web && npm run dev) & \
	(cd apps/lawchat && npm run dev) & \
	wait

dev-backend:
	@trap 'kill 0' INT; \
	uvicorn autocrawler_api.app:app --reload --port 8000 & \
	wait

dev-frontend:
	@trap 'kill 0' INT; \
	(cd apps/web && npm run dev) & \
	(cd apps/lawchat && npm run dev) & \
	wait

dev-api:
	uvicorn autocrawler_api.app:app --reload --port 8000

dev-web:
	cd apps/web && npm run dev

build-web:
	cd apps/web && npm run build

dev-lawchat:
	cd apps/lawchat && npm run dev

build-lawchat:
	cd apps/lawchat && npm run build

# Upload a single PDF into the running Docker API's ChromaDB.
# Usage: make docker-ingest FILE=建築法.pdf LAW_NAME=建築法
# LAW_NAME is optional; defaults to the filename stem.
docker-ingest:
	@test -n "$(FILE)" || (echo "ERROR: FILE is required. Usage: make docker-ingest FILE=path/to/law.pdf [LAW_NAME=法規名稱]" && exit 1)
	@test -f "$(FILE)" || (echo "ERROR: File not found: $(FILE)" && exit 1)
	@LAW_FIELD=$$([ -n "$(LAW_NAME)" ] && echo "-F law_name=$(LAW_NAME)" || echo ""); \
	curl -sf -X POST http://localhost:8000/rag/ingest \
	  -F "file=@$(FILE)" $$LAW_FIELD \
	  -F "embedding_provider=voyage" | python3 -m json.tool

# Upload all PDFs in a directory into the running Docker API's ChromaDB.
# Usage: make docker-ingest-all DIR=./pdfs
docker-ingest-all:
	@test -n "$(DIR)" || (echo "ERROR: DIR is required. Usage: make docker-ingest-all DIR=path/to/pdf_dir" && exit 1)
	@test -d "$(DIR)" || (echo "ERROR: Directory not found: $(DIR)" && exit 1)
	@count=0; \
	for f in "$(DIR)"/*.pdf; do \
	  [ -f "$$f" ] || continue; \
	  name=$$(basename "$$f" .pdf); \
	  echo ">>> Ingesting $$f ($$name)..."; \
	  curl -sf -X POST http://localhost:8000/rag/ingest \
	    -F "file=@$$f" \
	    -F "law_name=$$name" \
	    -F "embedding_provider=voyage" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  OK: {d[\"law_name\"]} — {d[\"chunk_count\"]} chunks')"; \
	  count=$$((count+1)); \
	done; \
	echo "Done. $$count file(s) ingested."

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
