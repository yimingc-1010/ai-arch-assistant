"""
API/Fetch 方式爬蟲
"""
import json
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse, parse_qs
import requests


class APIScraper:
    """透過 API/Fetch 方式取得資料"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def scrape(self, url: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        透過 API 取得資料

        Args:
            url: API 端點 URL
            config: 請求配置
                - method: HTTP 方法 (GET, POST, etc.)
                - headers: 額外的 headers
                - params: 查詢參數
                - data: POST 資料
                - json_data: JSON POST 資料
                - auth: 認證資訊

        Returns:
            Dict containing API response data
        """
        config = config or {}
        result = {
            'url': url,
            'success': False,
            'data': None,
            'raw_data': None,
            'data_type': None,
            'pagination': None,
            'error': None,
        }

        try:
            # 準備請求
            method = config.get('method', 'GET').upper()
            headers = config.get('headers', {})
            params = config.get('params', {})
            data = config.get('data')
            json_data = config.get('json_data')
            auth = config.get('auth')

            # 發送請求
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json_data,
                auth=auth,
                timeout=30,
            )
            response.raise_for_status()

            # 解析回應
            content_type = response.headers.get('Content-Type', '').lower()
            result['raw_data'] = response.text

            if 'application/json' in content_type or self._looks_like_json(response.text):
                result['data'] = response.json()
                result['data_type'] = 'json'
            elif 'xml' in content_type:
                result['data'] = self._parse_xml(response.text)
                result['data_type'] = 'xml'
            else:
                result['data'] = response.text
                result['data_type'] = 'text'

            # 偵測分頁資訊
            result['pagination'] = self._detect_pagination(response, result['data'])

            result['success'] = True

        except requests.RequestException as e:
            result['error'] = f'Request failed: {str(e)}'
        except json.JSONDecodeError as e:
            result['error'] = f'JSON parsing failed: {str(e)}'
        except Exception as e:
            result['error'] = f'Unexpected error: {str(e)}'

        return result

    def _looks_like_json(self, text: str) -> bool:
        """檢查文字是否看起來像 JSON"""
        text = text.strip()
        return (text.startswith('{') and text.endswith('}')) or \
               (text.startswith('[') and text.endswith(']'))

    def _parse_xml(self, xml_text: str) -> Dict[str, Any]:
        """簡單的 XML 轉 Dict"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_text)
            return self._element_to_dict(root)
        except Exception:
            return {'raw': xml_text}

    def _element_to_dict(self, element) -> Dict[str, Any]:
        """遞迴將 XML Element 轉換為 Dict"""
        result = {}

        # 屬性
        if element.attrib:
            result['@attributes'] = dict(element.attrib)

        # 子元素
        children = list(element)
        if children:
            child_dict = {}
            for child in children:
                child_data = self._element_to_dict(child)
                tag = child.tag

                if tag in child_dict:
                    if not isinstance(child_dict[tag], list):
                        child_dict[tag] = [child_dict[tag]]
                    child_dict[tag].append(child_data)
                else:
                    child_dict[tag] = child_data

            result.update(child_dict)
        elif element.text and element.text.strip():
            if result:
                result['#text'] = element.text.strip()
            else:
                return element.text.strip()

        return result

    def _detect_pagination(self, response: requests.Response, data: Any) -> Optional[Dict]:
        """偵測 API 分頁資訊"""
        pagination = {}

        # 從 headers 檢查
        link_header = response.headers.get('Link', '')
        if link_header:
            links = self._parse_link_header(link_header)
            if links:
                pagination['links'] = links

        # 從回應資料檢查
        if isinstance(data, dict):
            # 常見的分頁欄位
            page_fields = ['page', 'current_page', 'pageNumber']
            total_fields = ['total', 'total_count', 'totalCount', 'total_pages', 'totalPages']
            next_fields = ['next', 'next_page', 'nextPage', 'next_url', 'nextUrl']
            prev_fields = ['prev', 'previous', 'prev_page', 'prevPage', 'prev_url', 'prevUrl']

            for field in page_fields:
                if field in data:
                    pagination['current_page'] = data[field]
                    break

            for field in total_fields:
                if field in data:
                    pagination['total'] = data[field]
                    break

            for field in next_fields:
                if field in data and data[field]:
                    pagination['next'] = data[field]
                    break

            for field in prev_fields:
                if field in data and data[field]:
                    pagination['previous'] = data[field]
                    break

        return pagination if pagination else None

    def _parse_link_header(self, header: str) -> Dict[str, str]:
        """解析 Link header"""
        links = {}
        parts = header.split(',')

        for part in parts:
            match = re.match(r'<([^>]+)>;\s*rel="([^"]+)"', part.strip())
            if match:
                links[match.group(2)] = match.group(1)

        return links

    def discover_api(self, base_url: str) -> Dict[str, Any]:
        """
        嘗試自動發現 API 端點

        Args:
            base_url: 基礎 URL

        Returns:
            Dict containing discovered API information
        """
        result = {
            'base_url': base_url,
            'discovered_endpoints': [],
            'api_version': None,
        }

        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        # 常見的 API 路徑
        api_paths = [
            '/api',
            '/api/v1',
            '/api/v2',
            '/api/v3',
            '/v1',
            '/v2',
            '/graphql',
            '/rest',
        ]

        for path in api_paths:
            try:
                test_url = base + path
                response = self.session.get(test_url, timeout=5)
                if response.status_code in [200, 201]:
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'json' in content_type or 'xml' in content_type:
                        result['discovered_endpoints'].append({
                            'url': test_url,
                            'status': response.status_code,
                            'content_type': content_type,
                        })

                        # 嘗試偵測版本
                        version_match = re.search(r'/v(\d+)', path)
                        if version_match:
                            result['api_version'] = f'v{version_match.group(1)}'

            except requests.RequestException:
                continue

        return result


def scrape_api(url: str, config: Optional[Dict] = None) -> Dict[str, Any]:
    """便利函數：透過 API 取得資料"""
    scraper = APIScraper()
    return scraper.scrape(url, config)
