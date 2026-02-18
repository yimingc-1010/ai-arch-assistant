"""
法規專用提取器
支援全國法規資料庫 (law.moj.gov.tw) 與 ArkiTeki (arkiteki.com)
"""
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, parse_qs
import requests
from bs4 import BeautifulSoup


class LawScraper(ABC):
    """法規爬蟲基類"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        })

    @abstractmethod
    def scrape(self, url: str) -> Dict[str, Any]:
        """爬取法規頁面"""
        pass

    @abstractmethod
    def get_source(self) -> str:
        """返回來源網站識別"""
        pass

    def _create_result(self, url: str) -> Dict[str, Any]:
        """建立結果結構"""
        return {
            'url': url,
            'success': False,
            'data': {
                'source': self.get_source(),
                'law_name': None,
                'pcode': None,
                'last_modified': None,
                'chapters': [],
                'articles': [],
            },
            'error': None,
        }

    def _normalize_article_number(self, text: str) -> str:
        """正規化條號 (移除多餘空白)"""
        return re.sub(r'\s+', ' ', text.strip())

    def _normalize_content(self, text: str) -> str:
        """正規化內容 (移除多餘空白但保留換行)"""
        lines = text.split('\n')
        lines = [' '.join(line.split()) for line in lines]
        return '\n'.join(line for line in lines if line)


class MojLawScraper(LawScraper):
    """全國法規資料庫爬蟲 (law.moj.gov.tw)"""

    def get_source(self) -> str:
        return 'law.moj.gov.tw'

    def scrape(self, url: str) -> Dict[str, Any]:
        """
        爬取全國法規資料庫頁面

        HTML 結構:
        - 章節: <div class="h3 char-2">第 一 章 總則</div>
        - 條號: <div class="col-no"><a name="1">第 1 條</a></div>
        - 條文: <div class="col-data"><div class="law-article">...</div></div>
        """
        result = self._create_result(url)

        try:
            # 解析 pcode
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            if 'pcode' in query_params:
                result['data']['pcode'] = query_params['pcode'][0]

            # 發送請求
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # 自動偵測編碼
            if response.encoding == 'ISO-8859-1':
                response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'lxml')

            # 提取法規名稱
            result['data']['law_name'] = self._extract_law_name(soup)

            # 提取修正日期
            result['data']['last_modified'] = self._extract_last_modified(soup)

            # 提取章節與條文
            chapters, articles = self._extract_chapters_and_articles(soup)
            result['data']['chapters'] = chapters
            result['data']['articles'] = articles

            result['success'] = True

        except requests.RequestException as e:
            result['error'] = f'Request failed: {str(e)}'
        except Exception as e:
            result['error'] = f'Parsing failed: {str(e)}'

        return result

    def _extract_law_name(self, soup: BeautifulSoup) -> Optional[str]:
        """提取法規名稱"""
        # 嘗試從標題提取
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # 移除 "全國法規資料庫" 等字樣
            name = re.sub(r'-\s*全國法規資料庫.*$', '', title_text).strip()
            if name:
                return name

        # 嘗試從 h1 或特定 class 提取
        law_title = soup.find('h1', class_='law-title') or soup.find('h1')
        if law_title:
            return law_title.get_text(strip=True)

        return None

    def _extract_last_modified(self, soup: BeautifulSoup) -> Optional[str]:
        """提取最後修正日期"""
        # 尋找包含 "修正" 的文字
        modified_patterns = [
            r'民國\s*\d+\s*年\s*\d+\s*月\s*\d+\s*日',
        ]

        # 嘗試從 meta 或特定區塊提取
        for text in soup.stripped_strings:
            if '修正' in text or '公布' in text:
                for pattern in modified_patterns:
                    match = re.search(pattern, text)
                    if match:
                        return match.group(0)

        return None

    def _extract_chapters_and_articles(self, soup: BeautifulSoup) -> tuple:
        """提取章節與條文"""
        chapters = []
        articles = []
        current_chapter = None

        # 找到法規內容區塊
        content_div = soup.find('div', class_='law-reg-content') or soup.find('div', id='law-content') or soup

        # 遍歷所有相關元素
        # 章節標題: class="h3 char-2" 或 class="h3 char-3" 等
        # 條文區塊: class="row"

        # 先找所有章節標題
        chapter_divs = content_div.find_all('div', class_=re.compile(r'h3\s+char-'))
        for ch_div in chapter_divs:
            ch_text = ch_div.get_text(strip=True)
            # 解析章節號和標題
            ch_match = re.match(r'(第\s*[\d一二三四五六七八九十]+\s*章)\s*(.+)', ch_text)
            if ch_match:
                chapters.append({
                    'number': self._normalize_article_number(ch_match.group(1)),
                    'title': ch_match.group(2).strip(),
                })
            else:
                # 可能是編或節
                chapters.append({
                    'number': ch_text,
                    'title': '',
                })

        # 提取條文
        # 法規條文結構: <div class="row"> 包含 col-no 和 col-data
        rows = content_div.find_all('div', class_='row')
        for row in rows:
            col_no = row.find('div', class_='col-no')
            col_data = row.find('div', class_='col-data')

            if col_no and col_data:
                article_num = col_no.get_text(strip=True)
                if not re.match(r'第\s*[\d\-之]+\s*條', article_num):
                    continue

                # 取得條文內容
                law_article = col_data.find('div', class_='law-article')
                if law_article:
                    content_parts = []
                    items = []

                    for child in law_article.children:
                        if hasattr(child, 'get_text'):
                            text = child.get_text(strip=True)
                            # 檢查是否為項目 (一、二、三... 或 1. 2. 3...)
                            if re.match(r'^[一二三四五六七八九十]+、', text):
                                items.append(text)
                            elif re.match(r'^\d+\.', text):
                                items.append(text)
                            else:
                                content_parts.append(text)

                    content = '\n'.join(content_parts) if content_parts else col_data.get_text(strip=True)

                    articles.append({
                        'number': self._normalize_article_number(article_num),
                        'chapter': self._find_chapter_for_article(chapters, article_num, soup, row),
                        'content': self._normalize_content(content),
                        'items': items if items else None,
                    })

        # 如果上述方法沒找到條文，嘗試其他結構
        if not articles:
            articles = self._extract_articles_fallback(soup, chapters)

        return chapters, articles

    def _find_chapter_for_article(self, chapters: List[Dict], article_num: str,
                                   soup: BeautifulSoup, article_row) -> Optional[str]:
        """找出條文所屬章節"""
        if not chapters:
            return None

        # 透過 DOM 順序判斷
        # 找到此條文之前最近的章節標題
        prev_chapter = None
        for elem in article_row.find_all_previous():
            if hasattr(elem, 'get') and elem.get('class'):
                classes = elem.get('class', [])
                if any('h3' in c for c in classes) and any('char-' in c for c in classes):
                    prev_chapter = elem.get_text(strip=True)
                    break

        return prev_chapter

    def _extract_articles_fallback(self, soup: BeautifulSoup, chapters: List[Dict]) -> List[Dict]:
        """備用提取方法"""
        articles = []

        # 嘗試用 col-no 直接找
        col_nos = soup.find_all('div', class_='col-no')
        for col_no in col_nos:
            article_num = col_no.get_text(strip=True)
            if not re.match(r'第\s*[\d\-之]+\s*條', article_num):
                continue

            # 找相鄰的 col-data
            parent = col_no.parent
            if parent:
                col_data = parent.find('div', class_='col-data')
                if col_data:
                    content = col_data.get_text(separator='\n', strip=True)
                    articles.append({
                        'number': self._normalize_article_number(article_num),
                        'chapter': None,
                        'content': self._normalize_content(content),
                        'items': None,
                    })

        return articles


class ArkitekiScraper(LawScraper):
    """ArkiTeki 建築資料平台爬蟲 (arkiteki.com)"""

    def get_source(self) -> str:
        return 'arkiteki.com'

    def scrape(self, url: str) -> Dict[str, Any]:
        """
        爬取 ArkiTeki 法規頁面

        HTML 結構:
        - 法規表格: <table class="law-table">
        - 條號: <td class="law-no">第 1 條</td>
        - 條文: <td class="law-content" data-compound-no="第 1 條">...</td>
        """
        result = self._create_result(url)

        try:
            # 發送請求
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            if response.encoding == 'ISO-8859-1':
                response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'lxml')

            # 提取法規名稱
            result['data']['law_name'] = self._extract_law_name(soup, url)

            # 提取修正日期
            result['data']['last_modified'] = self._extract_last_modified(soup)

            # 提取章節與條文
            chapters, articles = self._extract_chapters_and_articles(soup)
            result['data']['chapters'] = chapters
            result['data']['articles'] = articles

            result['success'] = True

        except requests.RequestException as e:
            result['error'] = f'Request failed: {str(e)}'
        except Exception as e:
            result['error'] = f'Parsing failed: {str(e)}'

        return result

    def _extract_law_name(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """提取法規名稱"""
        # 從 h1 標題提取
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)

        # 從 title 提取
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # 移除網站名稱
            name = re.sub(r'\s*[|\-]\s*ArkiTeki.*$', '', title_text, flags=re.IGNORECASE).strip()
            if name:
                return name

        # 從 URL 提取
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[0] == 'term':
            return path_parts[1]

        return None

    def _extract_last_modified(self, soup: BeautifulSoup) -> Optional[str]:
        """提取最後修正日期"""
        # 尋找法規沿革或修正日期
        for text in soup.stripped_strings:
            if '修正' in text or '公布' in text:
                match = re.search(r'民國\s*\d+\s*年\s*\d+\s*月\s*\d+\s*日', text)
                if match:
                    return match.group(0)

        # 嘗試從特定元素提取
        history_div = soup.find('div', class_='law-history') or soup.find('div', class_='history')
        if history_div:
            match = re.search(r'民國\s*\d+\s*年\s*\d+\s*月\s*\d+\s*日', history_div.get_text())
            if match:
                return match.group(0)

        return None

    def _extract_chapters_and_articles(self, soup: BeautifulSoup) -> tuple:
        """提取章節與條文"""
        chapters = []
        articles = []
        current_chapter = None

        # 找法規表格
        law_table = soup.find('table', class_='law-table')
        if law_table:
            rows = law_table.find_all('tr')
            for row in rows:
                # 檢查是否為章節標題行
                if 'chapter' in row.get('class', []) or row.find('th'):
                    th = row.find('th')
                    if th:
                        ch_text = th.get_text(strip=True)
                        ch_match = re.match(r'(第\s*[\d一二三四五六七八九十]+\s*章)\s*(.+)?', ch_text)
                        if ch_match:
                            current_chapter = ch_text
                            chapters.append({
                                'number': self._normalize_article_number(ch_match.group(1)),
                                'title': (ch_match.group(2) or '').strip(),
                            })
                        continue

                # 提取條文
                law_no_td = row.find('td', class_='law-no')
                law_content_td = row.find('td', class_='law-content')

                if law_no_td and law_content_td:
                    article_num = law_no_td.get_text(strip=True)
                    content = law_content_td.get_text(separator='\n', strip=True)

                    # 提取項目
                    items = []
                    content_lines = content.split('\n')
                    main_content = []
                    for line in content_lines:
                        if re.match(r'^[一二三四五六七八九十]+、', line):
                            items.append(line)
                        elif re.match(r'^\d+\.', line):
                            items.append(line)
                        else:
                            main_content.append(line)

                    articles.append({
                        'number': self._normalize_article_number(article_num),
                        'chapter': current_chapter,
                        'content': self._normalize_content('\n'.join(main_content)),
                        'items': items if items else None,
                    })

        # 如果沒有 law-table，嘗試其他結構
        if not articles:
            articles = self._extract_articles_fallback(soup, chapters)

        return chapters, articles

    def _extract_articles_fallback(self, soup: BeautifulSoup, chapters: List[Dict]) -> List[Dict]:
        """備用提取方法 - 通用法規結構"""
        articles = []

        # 嘗試找所有看起來像條文的元素
        # 模式: "第 X 條" 後面跟著內容
        article_pattern = re.compile(r'第\s*[\d\-之]+\s*條')

        # 找所有包含條號的元素
        for elem in soup.find_all(string=article_pattern):
            parent = elem.parent
            if parent:
                article_num = elem.strip()
                # 取得下一個兄弟元素作為內容
                content_elem = parent.find_next_sibling()
                if content_elem:
                    content = content_elem.get_text(separator='\n', strip=True)
                    articles.append({
                        'number': self._normalize_article_number(article_num),
                        'chapter': None,
                        'content': self._normalize_content(content),
                        'items': None,
                    })

        return articles


def get_law_scraper(url: str) -> Optional[LawScraper]:
    """根據 URL 返回適合的法規爬蟲"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if 'law.moj.gov.tw' in domain:
        return MojLawScraper()
    elif 'arkiteki.com' in domain:
        return ArkitekiScraper()

    return None


def scrape_law(url: str) -> Dict[str, Any]:
    """便利函數: 爬取法規頁面"""
    scraper = get_law_scraper(url)
    if scraper:
        return scraper.scrape(url)

    return {
        'url': url,
        'success': False,
        'data': None,
        'error': f'Unsupported law website: {url}',
    }
