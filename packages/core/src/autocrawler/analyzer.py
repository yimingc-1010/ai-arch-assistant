"""
URL 分析器 - 判斷使用 HTML 解析還是 API Fetch 方式
"""
import re
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any
import requests

from autocrawler.registry import detect_strategy


class URLAnalyzer:
    """分析 URL 並決定最佳爬取策略"""

    # 常見的 API 路徑模式
    API_PATTERNS = [
        r'/api/',
        r'/v\d+/',
        r'/graphql',
        r'/rest/',
        r'/json',
        r'\.json$',
        r'/data/',
        r'/feed',
        r'/rss',
    ]

    # 常見的 API 子網域
    API_SUBDOMAINS = [
        'api',
        'data',
        'feeds',
        'rest',
        'graphql',
    ]

    # 常見的靜態內容指示
    STATIC_PATTERNS = [
        r'\.html?$',
        r'\.php$',
        r'\.asp$',
        r'\.jsp$',
        r'/page/',
        r'/post/',
        r'/article/',
        r'/blog/',
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def analyze(self, url: str) -> Dict[str, Any]:
        """
        分析 URL 並返回建議的爬取策略

        Returns:
            Dict containing:
            - strategy: 'api', 'html', or a registered strategy name
            - confidence: float (0-1)
            - reasons: list of reasons for the decision
            - api_endpoint: detected API endpoint if applicable
        """
        result = {
            'url': url,
            'strategy': 'html',
            'confidence': 0.5,
            'reasons': [],
            'api_endpoint': None,
            'content_type': None,
        }

        # 優先檢查已註冊的策略
        registered = detect_strategy(url)
        if registered:
            result['strategy'] = registered['strategy']
            result['confidence'] = 1.0
            result['reasons'].append(registered['reason'])
            return result

        parsed = urlparse(url)

        # 檢查 URL 模式
        api_score = self._check_url_patterns(url, parsed, result)

        # 嘗試發送 HEAD 請求檢查 Content-Type
        content_type_score = self._check_content_type(url, result)

        # 嘗試探測 API 端點
        api_probe_score = self._probe_api_endpoints(url, parsed, result)

        # 計算最終分數
        total_score = api_score + content_type_score + api_probe_score

        if total_score >= 0.6:
            result['strategy'] = 'api'
            result['confidence'] = min(total_score, 1.0)
        else:
            result['strategy'] = 'html'
            result['confidence'] = 1.0 - total_score

        return result

    def _check_url_patterns(self, url: str, parsed, result: Dict) -> float:
        """檢查 URL 是否符合 API 模式"""
        score = 0.0

        # 檢查子網域
        subdomain = parsed.netloc.split('.')[0] if '.' in parsed.netloc else ''
        if subdomain in self.API_SUBDOMAINS:
            score += 0.3
            result['reasons'].append(f'API subdomain detected: {subdomain}')

        # 檢查路徑模式
        for pattern in self.API_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                score += 0.25
                result['reasons'].append(f'API pattern matched: {pattern}')
                break

        # 檢查是否為靜態內容
        for pattern in self.STATIC_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                score -= 0.2
                result['reasons'].append(f'Static content pattern: {pattern}')
                break

        # 檢查查詢參數
        query_params = parse_qs(parsed.query)
        api_params = ['format', 'output', 'callback', 'token', 'key', 'api_key']
        for param in api_params:
            if param in query_params:
                score += 0.1
                result['reasons'].append(f'API parameter found: {param}')

        return max(0, score)

    def _check_content_type(self, url: str, result: Dict) -> float:
        """發送 HEAD 請求檢查 Content-Type"""
        score = 0.0
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            content_type = response.headers.get('Content-Type', '').lower()
            result['content_type'] = content_type

            if 'application/json' in content_type:
                score += 0.5
                result['reasons'].append('Content-Type is JSON')
            elif 'application/xml' in content_type or 'text/xml' in content_type:
                score += 0.3
                result['reasons'].append('Content-Type is XML')
            elif 'text/html' in content_type:
                score -= 0.1
                result['reasons'].append('Content-Type is HTML')

        except requests.RequestException as e:
            result['reasons'].append(f'HEAD request failed: {str(e)}')

        return score

    def _probe_api_endpoints(self, url: str, parsed, result: Dict) -> float:
        """嘗試探測可能的 API 端點"""
        score = 0.0
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # 常見的 API 端點
        api_endpoints = [
            '/api',
            '/api/v1',
            '/api/v2',
            f'/api{parsed.path}',
        ]

        for endpoint in api_endpoints:
            try:
                test_url = base_url + endpoint
                response = self.session.head(test_url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'json' in content_type or 'xml' in content_type:
                        score += 0.2
                        result['api_endpoint'] = test_url
                        result['reasons'].append(f'API endpoint found: {test_url}')
                        break
            except requests.RequestException:
                continue

        return score


def analyze_url(url: str) -> Dict[str, Any]:
    """便利函數：分析單一 URL"""
    analyzer = URLAnalyzer()
    return analyzer.analyze(url)
