"""
Batch ingest law texts from law.moj.gov.tw into the RAG system.

Usage:
    python scripts/batch_ingest_laws.py                    # ingest all known laws
    python scripts/batch_ingest_laws.py --dry-run          # test scraping only, no ingest
    python scripts/batch_ingest_laws.py --law 建築法        # ingest a single law
    python scripts/batch_ingest_laws.py --list             # list available laws with pcodes
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
PCODE_MAP_FILE = ROOT / "data" / "pcode_map.json"
LAWS_DIR = ROOT / "data" / "laws"

# Laws already ingested via PDF — skip to avoid duplication
SKIP_LAWS = {"建築物室內裝修管理辦法", "營造業法"}


def load_pcode_map() -> dict[str, str]:
    if not PCODE_MAP_FILE.exists():
        print(f"ERROR: pcode map not found at {PCODE_MAP_FILE}", file=sys.stderr)
        sys.exit(1)
    return json.loads(PCODE_MAP_FILE.read_text(encoding="utf-8"))


def articles_to_text(data: dict) -> str:
    """Convert MojLawScraper output to plain text with 第X條 markers."""
    parts = []
    for article in data.get("articles", []):
        lines = [article["number"], article["content"]]
        if article.get("items"):
            lines.extend(article["items"])
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def ingest_law(law_name: str, pcode: str, dry_run: bool = False) -> bool:
    """Scrape and ingest a single law. Returns True on success."""
    from autocrawler_law.scrapers import MojLawScraper

    url = f"https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={pcode}"
    print(f"  Scraping {law_name} ({pcode})...")

    scraper = MojLawScraper()
    result = scraper.scrape(url)

    if not result["success"]:
        print(f"  ERROR: scrape failed — {result.get('error')}")
        return False

    data = result["data"]
    scraped_name = data.get("law_name", law_name)
    articles_count = len(data.get("articles", []))
    full_text = articles_to_text(data)

    if not full_text.strip():
        print(f"  ERROR: empty text after scrape")
        return False

    print(f"  Scraped: {scraped_name} — {articles_count} articles, {len(full_text):,} chars")

    if dry_run:
        # Test chunking only
        from lawrag.pdf.chunker import chunk_document
        chunks = chunk_document(
            full_text=full_text,
            page_map={0: 1},
            law_name=law_name,
            source_file=f"web:{url}",
        )
        strategies = set(c.strategy for c in chunks)
        print(f"  [DRY RUN] Would produce {len(chunks)} chunks, strategies: {strategies}")
        return True

    # Full ingest via lawrag
    from lawrag.pipeline.ingestor import Ingestor
    ingestor = Ingestor()
    ingestor.ingest_text(
        full_text=full_text,
        law_name=law_name,
        source=f"web:law.moj.gov.tw/pcode={pcode}",
    )
    print(f"  Ingested: {law_name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Batch ingest laws from law.moj.gov.tw")
    parser.add_argument("--dry-run", action="store_true",
                        help="Test scraping + chunking only, skip embedding/store")
    parser.add_argument("--law", type=str, help="Ingest a single law by name")
    parser.add_argument("--list", action="store_true", help="List available laws")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Seconds to wait between requests (default: 2.0)")
    args = parser.parse_args()

    pcode_map = load_pcode_map()

    if args.list:
        print(f"Available laws ({len(pcode_map)} total):\n")
        for name, pcode in sorted(pcode_map.items()):
            skip = " [SKIP - already in PDF]" if name in SKIP_LAWS else ""
            print(f"  {pcode}  {name}{skip}")
        return

    if args.law:
        # Single law mode
        if args.law not in pcode_map:
            print(f"ERROR: '{args.law}' not in pcode_map. Run --list to see available laws.")
            sys.exit(1)
        pcode = pcode_map[args.law]
        success = ingest_law(args.law, pcode, dry_run=args.dry_run)
        sys.exit(0 if success else 1)

    # Batch mode
    to_process = {
        name: pcode for name, pcode in pcode_map.items()
        if name not in SKIP_LAWS
    }
    print(f"Batch ingesting {len(to_process)} laws (skipping {len(SKIP_LAWS)} already in PDF)\n")
    if args.dry_run:
        print("[DRY RUN MODE — no embedding/store writes]\n")

    success_count = 0
    fail_count = 0
    failed_laws = []

    for i, (name, pcode) in enumerate(sorted(to_process.items()), 1):
        print(f"[{i}/{len(to_process)}] {name}")
        try:
            ok = ingest_law(name, pcode, dry_run=args.dry_run)
            if ok:
                success_count += 1
            else:
                fail_count += 1
                failed_laws.append(name)
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            fail_count += 1
            failed_laws.append(name)

        if i < len(to_process):
            time.sleep(args.delay)

    print(f"\n{'='*50}")
    print(f"Done: {success_count} succeeded, {fail_count} failed")
    if failed_laws:
        print(f"Failed laws: {failed_laws}")


if __name__ == "__main__":
    main()
