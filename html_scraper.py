"""
HTML 結構解析爬蟲
"""
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup


class HTMLScraper:
    """透過 HTML 結構解析網頁內容"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def scrape(self, url: str, extract_config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        爬取並解析 HTML 頁面

        Args:
            url: 目標 URL
            extract_config: 自定義提取配置
                - title_selector: CSS selector for title
                - content_selector: CSS selector for main content
                - custom_selectors: Dict of {name: selector}

        Returns:
            Dict containing extracted data
        """
        result = {
            'url': url,
            'success': False,
            'data': {},
            'error': None,
        }

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # 自動偵測編碼
            if response.encoding == 'ISO-8859-1':
                response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'lxml')

            # 基本資料提取
            result['data'] = self._extract_basic_data(soup, url)

            # 自定義提取
            if extract_config:
                result['data'].update(self._extract_custom(soup, extract_config))

            # 自動偵測結構化資料
            result['data']['structured_data'] = self._extract_structured_data(soup)

            result['success'] = True

        except requests.RequestException as e:
            result['error'] = f'Request failed: {str(e)}'
        except Exception as e:
            result['error'] = f'Parsing failed: {str(e)}'

        return result

    def _extract_basic_data(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """提取基本頁面資料"""
        data = {
            'title': None,
            'description': None,
            'keywords': [],
            'headings': [],
            'links': [],
            'images': [],
            'text_content': None,
            'meta': {},
        }

        # 標題
        title_tag = soup.find('title')
        data['title'] = title_tag.get_text(strip=True) if title_tag else None

        # Meta 資料
        for meta in soup.find_all('meta'):
            name = meta.get('name', meta.get('property', ''))
            content = meta.get('content', '')
            if name and content:
                data['meta'][name] = content
                if name == 'description':
                    data['description'] = content
                elif name == 'keywords':
                    data['keywords'] = [k.strip() for k in content.split(',')]

        # Open Graph 資料
        og_data = {}
        for meta in soup.find_all('meta', property=re.compile(r'^og:')):
            prop = meta.get('property', '').replace('og:', '')
            og_data[prop] = meta.get('content', '')
        if og_data:
            data['meta']['og'] = og_data

        # 標題層級
        for i in range(1, 7):
            for heading in soup.find_all(f'h{i}'):
                text = heading.get_text(strip=True)
                if text:
                    data['headings'].append({
                        'level': i,
                        'text': text,
                    })

        # 連結
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                absolute_url = urljoin(url, href)
                data['links'].append({
                    'text': link.get_text(strip=True),
                    'url': absolute_url,
                    'is_external': urlparse(absolute_url).netloc != urlparse(url).netloc,
                })

        # 圖片
        for img in soup.find_all('img', src=True):
            src = img.get('src', '')
            if src:
                data['images'].append({
                    'src': urljoin(url, src),
                    'alt': img.get('alt', ''),
                    'title': img.get('title', ''),
                })

        # 主要文字內容
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            # 移除 script 和 style 標籤
            for tag in main_content.find_all(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            data['text_content'] = ' '.join(main_content.get_text(separator=' ', strip=True).split())

        return data

    def _extract_custom(self, soup: BeautifulSoup, config: Dict) -> Dict[str, Any]:
        """根據配置提取自定義內容"""
        data = {}

        if 'title_selector' in config:
            element = soup.select_one(config['title_selector'])
            data['custom_title'] = element.get_text(strip=True) if element else None

        if 'content_selector' in config:
            element = soup.select_one(config['content_selector'])
            data['custom_content'] = element.get_text(strip=True) if element else None

        if 'custom_selectors' in config:
            for name, selector in config['custom_selectors'].items():
                elements = soup.select(selector)
                if len(elements) == 1:
                    data[name] = elements[0].get_text(strip=True)
                elif len(elements) > 1:
                    data[name] = [el.get_text(strip=True) for el in elements]
                else:
                    data[name] = None

        return data

    def _extract_structured_data(self, soup: BeautifulSoup) -> List[Dict]:
        """提取結構化資料 (JSON-LD, Microdata)"""
        structured = []

        # JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                structured.append({
                    'type': 'json-ld',
                    'data': data,
                })
            except (json.JSONDecodeError, TypeError):
                continue

        return structured


def scrape_html(url: str, config: Optional[Dict] = None) -> Dict[str, Any]:
    """便利函數：爬取單一 HTML 頁面"""
    scraper = HTMLScraper()
    return scraper.scrape(url, config)
