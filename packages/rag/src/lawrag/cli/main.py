"""lawrag CLI — ingest / query / list commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _build_store(chroma_dir: str | None = None):
    from lawrag.store.chroma import LawChromaStore
    from lawrag import config

    directory = chroma_dir or config.get_chroma_dir()
    return LawChromaStore(persist_dir=directory)


def cmd_ingest(args: argparse.Namespace) -> int:
    from lawrag.providers import get_embedding_provider
    from lawrag.pipeline.ingestor import Ingestor

    store = _build_store(args.chroma_dir)
    embedder = get_embedding_provider(args.embedding_provider)
    ingestor = Ingestor(store=store, embedder=embedder)

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        return 1

    chunks = ingestor.ingest(
        pdf_path=pdf_path,
        law_name=args.law_name or None,
        verbose=args.verbose,
    )

    if not args.verbose:
        print(f"Ingested {len(chunks)} chunks from {pdf_path.name}")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    from lawrag.providers import get_embedding_provider, get_llm_provider
    from lawrag.pipeline.retriever import Retriever

    store = _build_store(args.chroma_dir)
    embedder = get_embedding_provider(args.embedding_provider)
    llm = get_llm_provider(args.llm_provider)
    retriever = Retriever(store=store, embedder=embedder, llm=llm)

    law_names = args.law if args.law else None

    response = retriever.query(
        question=args.question,
        law_names=law_names,
        n_results=args.n_results,
    )

    if args.format == "json":
        output = {
            "answer": response.answer,
            "llm_provider": response.llm_provider,
            "model": response.model,
            "retrieved_chunk_count": response.retrieved_chunk_count,
            "sources": [
                {
                    "law_name": s.law_name,
                    "article_number": s.article_number,
                    "chapter": s.chapter,
                    "text": s.text,
                    "score": s.score,
                    "page": s.page,
                }
                for s in response.sources
            ],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(response.answer)
        if response.sources:
            print("\n── 來源 ──")
            for src in response.sources:
                ref = f"【{src.law_name}】"
                if src.chapter:
                    ref += f" {src.chapter}"
                if src.article_number:
                    ref += f" {src.article_number}"
                print(f"  {ref}  (p.{src.page}, score={src.score:.4f})")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    store = _build_store(args.chroma_dir)
    documents = store.list_documents()

    if args.json:
        print(json.dumps(documents, ensure_ascii=False, indent=2))
    else:
        if not documents:
            print("No documents ingested yet.")
        else:
            print(f"{'Law name':<30} {'Chunks':>7}  Ingested at")
            print("-" * 60)
            for doc in documents:
                print(
                    f"{doc.get('law_name', ''):<30} "
                    f"{doc.get('chunk_count', '?'):>7}  "
                    f"{doc.get('ingested_at', '')}"
                )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lawrag",
        description="RAG system for Traditional Chinese law regulations",
    )
    parser.add_argument(
        "--chroma-dir",
        default=None,
        help="ChromaDB persist directory (default: LAWRAG_CHROMA_DIR or ./data/chroma)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── ingest ──────────────────────────────────────────────────────────
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a law PDF into the vector store")
    ingest_parser.add_argument("pdf_path", help="Path to the PDF file")
    ingest_parser.add_argument("--law-name", default=None, help="Override the law name")
    ingest_parser.add_argument(
        "--embedding-provider",
        default=None,
        choices=["voyage", "openai"],
        help="Embedding provider (default: LAWRAG_EMBEDDING_PROVIDER or voyage)",
    )
    ingest_parser.add_argument("-v", "--verbose", action="store_true")

    # ── query ───────────────────────────────────────────────────────────
    query_parser = subparsers.add_parser("query", help="Ask a legal question")
    query_parser.add_argument("question", help="Question in Traditional Chinese")
    query_parser.add_argument(
        "--law",
        action="append",
        metavar="LAW_NAME",
        help="Filter to this law (may be repeated for multiple laws)",
    )
    query_parser.add_argument(
        "--n-results",
        type=int,
        default=5,
        help="Number of chunks to retrieve (default: 5)",
    )
    query_parser.add_argument(
        "--embedding-provider",
        default=None,
        choices=["voyage", "openai"],
    )
    query_parser.add_argument(
        "--llm-provider",
        default=None,
        choices=["anthropic", "openai"],
    )
    query_parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json"],
        help="Output format (default: text)",
    )
    query_parser.add_argument("--chroma-dir", default=None)

    # ── list ────────────────────────────────────────────────────────────
    list_parser = subparsers.add_parser("list", help="List ingested law documents")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")
    list_parser.add_argument("--chroma-dir", default=None)

    args = parser.parse_args()

    # Route to the right handler
    handlers = {
        "ingest": cmd_ingest,
        "query": cmd_query,
        "list": cmd_list,
    }

    exit_code = handlers[args.command](args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
