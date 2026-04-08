"""Download law PDFs from law.moj.gov.tw into data/laws/.

Usage:
    python scripts/download_law_pdfs.py --dry-run     # show what would be downloaded
    python scripts/download_law_pdfs.py               # download all missing PDFs
    python scripts/download_law_pdfs.py --law 建築法  # single law
"""
import argparse
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
PCODE_MAP_FILE = ROOT / "data" / "pcode_map.json"
LAWS_DIR = ROOT / "data" / "laws"

BASE_URL = "https://law.moj.gov.tw"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}


def fetch_pdf_bytes(pcode: str, session: requests.Session, debug: bool = False) -> bytes | None:
    """POST the FilesType form with PDF selected, return raw PDF bytes."""
    files_url = f"{BASE_URL}/LawClass/FilesType.aspx?DataId={pcode}&SLI=CALL&FT=PDF"

    # Step 1: GET the form to collect ASP.NET hidden fields
    try:
        r = session.get(files_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching FilesType page: {e}")
        return None

    soup = BeautifulSoup(r.text, "lxml")

    # Extract all hidden form inputs (ViewState, EventValidation, etc.)
    form_data: dict[str, str] = {}
    for inp in soup.find_all("input"):
        name = inp.get("name", "")
        val = inp.get("value", "")
        if name:
            form_data[name] = val

    if debug:
        print(f"  [DEBUG] Form fields: {list(form_data.keys())}")

    # Override to select PDF
    form_data["rdoFilesType"] = "PDF"
    # Find the submit/download button name
    for btn in soup.find_all(["input", "button"]):
        btn_type = btn.get("type", "").lower()
        btn_name = btn.get("name", "")
        btn_val = btn.get("value", btn.get_text(strip=True))
        if btn_type == "submit" or "下載" in btn_val:
            if btn_name:
                form_data[btn_name] = btn_val
            if debug:
                print(f"  [DEBUG] Submit button: name={btn_name!r} value={btn_val!r}")
            break

    if debug:
        print(f"  [DEBUG] POSTing to: {files_url}")
        print(f"  [DEBUG] POST data: {form_data}")

    # Step 2: POST the form
    post_headers = {**HEADERS, "Referer": files_url, "Content-Type": "application/x-www-form-urlencoded"}
    try:
        r2 = session.post(files_url, data=form_data, headers=post_headers, timeout=30, allow_redirects=True)
        r2.raise_for_status()
    except Exception as e:
        print(f"  ERROR during POST: {e}")
        return None

    content_type = r2.headers.get("Content-Type", "")
    if debug:
        print(f"  [DEBUG] POST response: status={r2.status_code} Content-Type={content_type!r} size={len(r2.content)}")

    if "pdf" in content_type.lower() or "octet" in content_type.lower():
        return r2.content

    # Response might redirect or contain a link to the actual PDF
    if "html" in content_type.lower():
        soup2 = BeautifulSoup(r2.text, "lxml")
        for a in soup2.find_all("a", href=True):
            href = a["href"]
            if re.search(r"(LawGetFile\.ashx|\.pdf)", href, re.IGNORECASE):
                pdf_url = href if href.startswith("http") else f"{BASE_URL}/LawClass/{href.lstrip('./')}"
                if debug:
                    print(f"  [DEBUG] Found PDF link in response: {pdf_url}")
                r3 = session.get(pdf_url, headers=HEADERS, timeout=30)
                if r3.ok:
                    return r3.content
        m = re.search(r"(LawGetFile\.ashx\?[^'\"&\s]+)", r2.text, re.IGNORECASE)
        if m:
            pdf_url = f"{BASE_URL}/LawClass/{m.group(1)}"
            if debug:
                print(f"  [DEBUG] Found PDF URL in JS: {pdf_url}")
            r3 = session.get(pdf_url, headers=HEADERS, timeout=30)
            if r3.ok:
                return r3.content
        if debug:
            for line in r2.text.splitlines():
                if re.search(r"(GetFile|\.pdf|FileId)", line, re.IGNORECASE):
                    print(f"  [DEBUG] response HTML: {line.strip()[:120]}")

    return None


def already_downloaded(law_name: str) -> Path | None:
    for p in LAWS_DIR.glob("*.pdf"):
        if law_name in p.stem:
            return p
    return None


def save_pdf(law_name: str, data: bytes) -> bool:
    dest = LAWS_DIR / f"{law_name}.pdf"
    LAWS_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    size_kb = len(data) // 1024
    print(f"  Saved: {dest.name} ({size_kb} KB)")
    return True


def process_law(law_name: str, pcode: str, session: requests.Session, dry_run: bool, debug: bool = False) -> bool:
    existing = already_downloaded(law_name)
    if existing:
        print(f"  SKIP (already exists: {existing.name})")
        return True

    pdf_bytes = fetch_pdf_bytes(pcode, session, debug=debug)
    if not pdf_bytes:
        print(f"  ERROR: failed to retrieve PDF")
        return False

    if dry_run:
        print(f"  [DRY RUN] Would save {len(pdf_bytes):,} bytes → {law_name}.pdf")
        return True

    return save_pdf(law_name, pdf_bytes)


def main():
    parser = argparse.ArgumentParser(description="Download law PDFs from law.moj.gov.tw")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without downloading")
    parser.add_argument("--law", type=str, help="Process a single law by name")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between requests (default: 1.5)")
    parser.add_argument("--debug", action="store_true", help="Print all links found on each page")
    args = parser.parse_args()

    pcode_map: dict[str, str] = json.loads(PCODE_MAP_FILE.read_text(encoding="utf-8"))
    session = requests.Session()

    if args.law:
        if args.law not in pcode_map:
            print(f"ERROR: '{args.law}' not in pcode_map. Available: {sorted(pcode_map)}")
            return
        laws = {args.law: pcode_map[args.law]}
    else:
        laws = pcode_map

    if args.dry_run:
        print(f"[DRY RUN] Checking {len(laws)} laws for PDF links\n")

    success, fail = 0, 0
    for i, (name, pcode) in enumerate(sorted(laws.items()), 1):
        print(f"[{i}/{len(laws)}] {name} ({pcode})")
        ok = process_law(name, pcode, session, dry_run=args.dry_run, debug=args.debug)
        if ok:
            success += 1
        else:
            fail += 1

        if i < len(laws):
            time.sleep(args.delay)

    print(f"\n{'='*50}")
    print(f"OK: {success}  Failed: {fail}")


if __name__ == "__main__":
    main()
