"""
自動爬蟲整合測試
"""
import json
import pytest
import responses

from autocrawler.crawler import AutoCrawler, crawl


class TestAutoCrawler:
    """自動爬蟲整合測試"""

    @responses.activate
    def test_auto_html_strategy(self):
        """測試自動選擇 HTML 策略"""
        url = 'https://example.com/blog/post-1'

        # HEAD 請求
        responses.add(responses.HEAD, url, status=200,
                      headers={'Content-Type': 'text/html'})

        # GET 請求
        html_content = '''
        <html>
        <head><title>Blog Post</title></head>
        <body><h1>Article Title</h1><p>Content</p></body>
        </html>
        '''
        responses.add(responses.GET, url, body=html_content, status=200,
                      content_type='text/html')

        result = crawl(url)

        assert result['success'] is True
        assert result['strategy_used'] == 'html'
        assert result['data']['title'] == 'Blog Post'

    @responses.activate
    def test_auto_api_strategy(self):
        """測試自動選擇 API 策略"""
        url = 'https://api.example.com/v1/users'

        # HEAD 請求
        responses.add(responses.HEAD, url, status=200,
                      headers={'Content-Type': 'application/json'})

        # GET 請求
        responses.add(responses.GET, url, json={'users': []}, status=200,
                      content_type='application/json')

        result = crawl(url)

        assert result['success'] is True
        assert result['strategy_used'] == 'api'

    @responses.activate
    def test_force_strategy(self):
        """測試強制策略"""
        url = 'https://example.com/data'

        html_content = '<html><body>Data</body></html>'
        responses.add(responses.GET, url, body=html_content, status=200)

        result = crawl(url, force_strategy='html')

        assert result['strategy_used'] == 'html'
        assert result['strategy_analysis']['forced'] is True

    @responses.activate
    def test_fallback_to_html(self):
        """測試 API 失敗後回退到 HTML"""
        url = 'https://api.example.com/data'

        # HEAD 返回 JSON
        responses.add(responses.HEAD, url, status=200,
                      headers={'Content-Type': 'application/json'})

        # GET 返回 HTML (API 失敗)
        responses.add(responses.GET, url, body='<html><body>Fallback</body></html>',
                      status=200, content_type='text/html')

        # 第二次 GET (HTML fallback)
        responses.add(responses.GET, url, body='<html><body>Fallback</body></html>',
                      status=200, content_type='text/html')

        crawler = AutoCrawler()
        result = crawler.crawl(url)

        # 應該成功（使用 HTML fallback）
        assert result['success'] is True

    @responses.activate
    def test_json_output_format(self):
        """測試 JSON 輸出格式"""
        url = 'https://example.com/page'

        responses.add(responses.HEAD, url, status=200,
                      headers={'Content-Type': 'text/html'})

        html_content = '<html><head><title>Test</title></head><body></body></html>'
        responses.add(responses.GET, url, body=html_content, status=200)

        crawler = AutoCrawler()
        result = crawler.crawl(url)

        # 驗證結構
        assert 'url' in result
        assert 'timestamp' in result
        assert 'strategy_analysis' in result
        assert 'strategy_used' in result
        assert 'success' in result
        assert 'data' in result

        # 驗證可以轉成 JSON
        json_str = crawler.to_json(result)
        parsed = json.loads(json_str)
        assert parsed['url'] == url

    @responses.activate
    def test_multiple_urls(self):
        """測試多 URL 爬取"""
        urls = [
            'https://example.com/page1',
            'https://example.com/page2',
        ]

        for url in urls:
            responses.add(responses.HEAD, url, status=200,
                          headers={'Content-Type': 'text/html'})
            responses.add(responses.GET, url,
                          body=f'<html><title>{url}</title></html>',
                          status=200)

        crawler = AutoCrawler()
        results = crawler.crawl_multiple(urls)

        assert len(results) == 2
        assert all(r['success'] for r in results)


class TestErrorHandling:
    """錯誤處理測試"""

    @responses.activate
    def test_network_error(self):
        """測試網路錯誤處理"""
        url = 'https://example.com/error'

        responses.add(responses.HEAD, url, status=200)
        responses.add(responses.GET, url,
                      body=Exception('Network error'))

        result = crawl(url, force_strategy='html')

        assert result['success'] is False
        assert result['error'] is not None

    @responses.activate
    def test_invalid_json(self):
        """測試無效 JSON 處理"""
        url = 'https://api.example.com/bad-json'

        responses.add(responses.HEAD, url, status=200,
                      headers={'Content-Type': 'application/json'})
        responses.add(responses.GET, url, body='not valid json',
                      status=200, content_type='application/json')

        result = crawl(url, force_strategy='api')

        # 應該處理錯誤而不是崩潰
        assert 'error' in result or result['success'] is False

    @responses.activate
    def test_http_error(self):
        """測試 HTTP 錯誤處理"""
        url = 'https://example.com/404'

        responses.add(responses.HEAD, url, status=200)
        responses.add(responses.GET, url, status=404)

        result = crawl(url, force_strategy='html')

        assert result['success'] is False
        assert result['error'] is not None
