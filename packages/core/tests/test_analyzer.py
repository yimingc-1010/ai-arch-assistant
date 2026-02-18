"""
URL 分析器測試
"""
import pytest
import responses
from unittest.mock import patch, MagicMock

from autocrawler.analyzer import URLAnalyzer, analyze_url


class TestURLAnalyzer:
    """URL 分析器測試"""

    def test_api_pattern_detection(self):
        """測試 API 路徑模式偵測"""
        analyzer = URLAnalyzer()

        # API 路徑
        api_urls = [
            'https://example.com/api/users',
            'https://example.com/v1/data',
            'https://example.com/graphql',
            'https://example.com/data.json',
        ]

        for url in api_urls:
            with patch.object(analyzer.session, 'head') as mock_head:
                mock_head.return_value = MagicMock(
                    headers={'Content-Type': 'text/html'},
                    status_code=200
                )
                result = analyzer.analyze(url)
                # API 模式應該被偵測到
                assert any('API' in r or 'api' in r.lower() for r in result['reasons']), \
                    f"API pattern should be detected for {url}"

    def test_static_pattern_detection(self):
        """測試靜態內容模式偵測"""
        analyzer = URLAnalyzer()

        static_urls = [
            'https://example.com/page/about.html',
            'https://example.com/blog/post-1',
            'https://example.com/article/news',
        ]

        for url in static_urls:
            with patch.object(analyzer.session, 'head') as mock_head:
                mock_head.return_value = MagicMock(
                    headers={'Content-Type': 'text/html'},
                    status_code=200
                )
                result = analyzer.analyze(url)
                # 應該傾向 HTML 策略
                assert result['strategy'] == 'html' or 'static' in str(result['reasons']).lower()

    def test_api_subdomain_detection(self):
        """測試 API 子網域偵測"""
        analyzer = URLAnalyzer()

        with patch.object(analyzer.session, 'head') as mock_head:
            mock_head.return_value = MagicMock(
                headers={'Content-Type': 'application/json'},
                status_code=200
            )
            result = analyzer.analyze('https://api.example.com/users')
            assert 'api' in str(result['reasons']).lower()

    @responses.activate
    def test_content_type_json_detection(self):
        """測試 JSON Content-Type 偵測"""
        url = 'https://example.com/data'
        responses.add(
            responses.HEAD,
            url,
            headers={'Content-Type': 'application/json'},
            status=200
        )

        analyzer = URLAnalyzer()
        result = analyzer.analyze(url)
        assert result['content_type'] == 'application/json'
        assert 'JSON' in str(result['reasons'])
