"""Scan law.moj.gov.tw to build a name → pcode mapping for target laws."""
import json
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

TARGET_LAWS = {
    # 建築法規
    "建築法", "建築師法", "建築基地法定空地分割辦法", "建築師法施行細則",
    "建築物室內裝修管理辦法", "建築物昇降設備設置及檢查管理辦法",
    "建築物使用類組及變更使用辦法", "建築物公共安全查驗及申報辦法",
    "建造執照預審辦法", "建築執照處理辦法", "建築部分使用執照核發辦法",
    "供公眾使用建築物之範圍", "招牌廣告及樹立廣告管理辦法",
    "原有合法建築物防火避難設施及消防設備改善辦法",
    "公寓大廈管理條例", "公寓大廈管理條例施行細則",
    "大眾捷運法", "大眾捷運系統土地開發辦法", "大眾捷運系統兩側禁建限建辦法",
    "實施區域計畫地區建築管理辦法", "實施都市計畫以外地區建築物管理辦法",
    "消防法", "消防法施行細則",
    # 區域計畫/非都市
    "區域計畫法", "區域計畫法施行細則",
    "非都市土地使用管制規則", "水土保持法", "水土保持法施行細則",
    "農業用地興建農舍辦法",
    # 都市計畫
    "都市計畫法", "都市計畫法臺灣省施行細則",
    # 都市更新
    "都市更新條例", "都市更新條例施行細則",
    "不動產證券化條例", "不動產證券化條例施行細則",
    # 國家公園/山坡地
    "國家公園法", "國家公園法施行細則",
    "山坡地建築管理辦法", "山坡地保育利用條例", "山坡地保育利用條例施行細則",
    # 環評/採購
    "環境影響評估法", "環境影響評估法施行細則",
    "政府採購法", "政府採購法施行細則",
    # 建築師/技師/營造
    "技師法", "技師法施行細則",
    "建築物結構與設備專業工程技師簽證規則", "公共工程專業技師簽證規則",
    "營造業法", "營造業法施行細則",
    "營繕工程承攬契約應記載事項實施辦法",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

CACHE_FILE = Path(__file__).parent.parent / "data" / "pcode_map.json"


def get_law_name(pcode: str, session: requests.Session) -> str | None:
    try:
        r = session.get(
            f"https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={pcode}",
            headers=HEADERS, timeout=10
        )
        soup = BeautifulSoup(r.text, "lxml")
        title = soup.find("title")
        if title:
            name = title.get_text(strip=True).replace("-全國法規資料庫", "").strip()
            return name if name else None
    except Exception:
        pass
    return None


def scan_range(prefixes: list[str], start: int, end: int) -> dict[str, str]:
    """Return {law_name: pcode} for laws found in scanned range."""
    found = {}
    session = requests.Session()
    for prefix in prefixes:
        for n in range(start, end + 1):
            pcode = f"{prefix}{n:04d}"
            name = get_law_name(pcode, session)
            if name and name in TARGET_LAWS:
                print(f"  FOUND: {pcode} = {name}")
                found[name] = pcode
            elif name:
                pass  # not a target law
            time.sleep(0.3)  # polite rate limiting
    return found


if __name__ == "__main__":
    existing = {}
    if CACHE_FILE.exists():
        existing = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        print(f"Loaded {len(existing)} existing mappings from cache")

    remaining = TARGET_LAWS - set(existing.keys())
    print(f"Need to find: {len(remaining)} laws")
    for name in sorted(remaining):
        print(f"  - {name}")

    if not remaining:
        print("All laws found!")
    else:
        print("\nScanning D0070xxx (內政部 建築/都市) range 1-250...")
        found = scan_range(["D0070"], 1, 250)
        existing.update(found)

        remaining = TARGET_LAWS - set(existing.keys())
        if remaining:
            print("\nScanning A0030xxx (工程會 採購) range 1-30...")
            found = scan_range(["A0030"], 1, 30)
            existing.update(found)

        remaining = TARGET_LAWS - set(existing.keys())
        if remaining:
            print("\nScanning G0030xxx (環保署) range 1-30...")
            found = scan_range(["G0030"], 1, 30)
            existing.update(found)

        remaining = TARGET_LAWS - set(existing.keys())
        if remaining:
            print("\nScanning K0060xxx (技師/建築師) range 1-50...")
            found = scan_range(["K0060"], 1, 50)
            existing.update(found)

    CACHE_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {len(existing)} mappings to {CACHE_FILE}")
    print("\nMissing:")
    for name in sorted(TARGET_LAWS - set(existing.keys())):
        print(f"  - {name}")
