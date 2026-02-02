"""
法規輸出模組
支援 CSV 格式輸出
"""
import csv
import io
from typing import Dict, Any, List


def export_csv(law_data: Dict[str, Any]) -> str:
    """
    將法規資料輸出為 CSV 格式

    Args:
        law_data: 法規資料字典，包含 articles 列表

    Returns:
        CSV 格式字串

    輸出格式:
        條號, 章節, 條文內容
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    # 寫入標題行
    writer.writerow(['條號', '章節', '條文內容'])

    # 寫入條文
    articles = law_data.get('articles', [])
    for article in articles:
        number = article.get('number', '')
        chapter = article.get('chapter', '') or ''
        content = article.get('content', '')

        # 如果有項目，將項目附加到內容
        items = article.get('items')
        if items:
            content = content + '\n' + '\n'.join(items)

        writer.writerow([number, chapter, content])

    return output.getvalue()


def export_csv_file(law_data: Dict[str, Any], filepath: str) -> None:
    """
    將法規資料輸出為 CSV 檔案

    Args:
        law_data: 法規資料字典
        filepath: 輸出檔案路徑
    """
    csv_content = export_csv(law_data)
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        f.write(csv_content)


def export_detailed_csv(law_data: Dict[str, Any]) -> str:
    """
    將法規資料輸出為詳細 CSV 格式 (包含更多欄位)

    Args:
        law_data: 法規資料字典

    Returns:
        CSV 格式字串

    輸出格式:
        法規名稱, 條號, 章節, 條文內容, 項目數
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    law_name = law_data.get('law_name', '')

    # 寫入標題行
    writer.writerow(['法規名稱', '條號', '章節', '條文內容', '項目數'])

    # 寫入條文
    articles = law_data.get('articles', [])
    for article in articles:
        number = article.get('number', '')
        chapter = article.get('chapter', '') or ''
        content = article.get('content', '')
        items = article.get('items') or []
        item_count = len(items)

        # 將項目附加到內容
        if items:
            content = content + '\n' + '\n'.join(items)

        writer.writerow([law_name, number, chapter, content, item_count])

    return output.getvalue()
