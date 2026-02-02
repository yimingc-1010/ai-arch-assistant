"""
自動爬蟲測試腳本
"""
import json
import pytest
import responses
from unittest.mock import patch, MagicMock

from url_analyzer import URLAnalyzer, analyze_url
from html_scraper import HTMLScraper, scrape_html
from api_scraper import APIScraper, scrape_api
from crawler import AutoCrawler, crawl


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


class TestHTMLScraper:
    """HTML 爬蟲測試"""

    @responses.activate
    def test_basic_html_extraction(self):
        """測試基本 HTML 資料提取"""
        url = 'https://example.com/page'
        html_content = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page Title</title>
            <meta name="description" content="Test description">
            <meta name="keywords" content="test, keywords, example">
        </head>
        <body>
            <main>
                <h1>Main Heading</h1>
                <h2>Sub Heading</h2>
                <p>This is test content.</p>
                <a href="/link1">Internal Link</a>
                <a href="https://external.com/page">External Link</a>
                <img src="/image.jpg" alt="Test Image">
            </main>
        </body>
        </html>
        '''

        responses.add(responses.GET, url, body=html_content, status=200,
                      content_type='text/html')

        result = scrape_html(url)

        assert result['success'] is True
        assert result['data']['title'] == 'Test Page Title'
        assert result['data']['description'] == 'Test description'
        assert 'test' in result['data']['keywords']
        assert len(result['data']['headings']) >= 2
        assert result['data']['headings'][0]['level'] == 1
        assert result['data']['headings'][0]['text'] == 'Main Heading'

    @responses.activate
    def test_link_extraction(self):
        """測試連結提取"""
        url = 'https://example.com/page'
        html_content = '''
        <html><body>
            <a href="/internal">Internal</a>
            <a href="https://external.com">External</a>
            <a href="#anchor">Anchor</a>
            <a href="javascript:void(0)">JS Link</a>
        </body></html>
        '''

        responses.add(responses.GET, url, body=html_content, status=200)

        result = scrape_html(url)
        links = result['data']['links']

        # 應該只有兩個有效連結（排除 anchor 和 javascript）
        assert len(links) == 2
        assert any(l['url'] == 'https://example.com/internal' for l in links)
        assert any(l['is_external'] for l in links)

    @responses.activate
    def test_custom_selector_extraction(self):
        """測試自定義選擇器提取"""
        url = 'https://example.com/page'
        html_content = '''
        <html><body>
            <div class="product-title">Product Name</div>
            <span class="price">$99.99</span>
            <div class="item">Item 1</div>
            <div class="item">Item 2</div>
        </body></html>
        '''

        responses.add(responses.GET, url, body=html_content, status=200)

        config = {
            'custom_selectors': {
                'product': '.product-title',
                'price': '.price',
                'items': '.item',
            }
        }

        result = scrape_html(url, config)

        assert result['data']['product'] == 'Product Name'
        assert result['data']['price'] == '$99.99'
        assert isinstance(result['data']['items'], list)
        assert len(result['data']['items']) == 2

    @responses.activate
    def test_structured_data_extraction(self):
        """測試結構化資料 (JSON-LD) 提取"""
        url = 'https://example.com/page'
        html_content = '''
        <html><head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Test Product"
            }
            </script>
        </head><body></body></html>
        '''

        responses.add(responses.GET, url, body=html_content, status=200)

        result = scrape_html(url)
        structured = result['data']['structured_data']

        assert len(structured) == 1
        assert structured[0]['type'] == 'json-ld'
        assert structured[0]['data']['@type'] == 'Product'


class TestAPIScraper:
    """API 爬蟲測試"""

    @responses.activate
    def test_json_api_scraping(self):
        """測試 JSON API 爬取"""
        url = 'https://api.example.com/users'
        json_data = {
            'users': [
                {'id': 1, 'name': 'Alice'},
                {'id': 2, 'name': 'Bob'},
            ],
            'total': 2
        }

        responses.add(
            responses.GET, url,
            json=json_data,
            status=200,
            content_type='application/json'
        )

        result = scrape_api(url)

        assert result['success'] is True
        assert result['data_type'] == 'json'
        assert result['data']['total'] == 2
        assert len(result['data']['users']) == 2

    @responses.activate
    def test_pagination_detection(self):
        """測試分頁偵測"""
        url = 'https://api.example.com/items'
        json_data = {
            'items': [],
            'page': 1,
            'total_pages': 10,
            'next_page': 'https://api.example.com/items?page=2'
        }

        responses.add(
            responses.GET, url,
            json=json_data,
            status=200,
            content_type='application/json'
        )

        result = scrape_api(url)

        assert result['pagination'] is not None
        assert result['pagination']['current_page'] == 1
        assert result['pagination']['total'] == 10
        assert 'page=2' in result['pagination']['next']

    @responses.activate
    def test_link_header_pagination(self):
        """測試 Link Header 分頁"""
        url = 'https://api.example.com/items'

        responses.add(
            responses.GET, url,
            json={'items': []},
            status=200,
            content_type='application/json',
            headers={
                'Link': '<https://api.example.com/items?page=2>; rel="next", '
                        '<https://api.example.com/items?page=10>; rel="last"'
            }
        )

        result = scrape_api(url)

        assert result['pagination'] is not None
        assert 'links' in result['pagination']
        assert 'next' in result['pagination']['links']

    @responses.activate
    def test_xml_parsing(self):
        """測試 XML 解析"""
        url = 'https://api.example.com/feed'
        xml_content = '''<?xml version="1.0"?>
        <root>
            <item>
                <name>Test</name>
                <value>123</value>
            </item>
        </root>
        '''

        responses.add(
            responses.GET, url,
            body=xml_content,
            status=200,
            content_type='application/xml'
        )

        result = scrape_api(url)

        assert result['success'] is True
        assert result['data_type'] == 'xml'
        assert 'item' in result['data']

    @responses.activate
    def test_post_request(self):
        """測試 POST 請求"""
        url = 'https://api.example.com/create'

        responses.add(
            responses.POST, url,
            json={'success': True, 'id': 123},
            status=201,
            content_type='application/json'
        )

        config = {
            'method': 'POST',
            'json_data': {'name': 'test'}
        }

        result = scrape_api(url, config)

        assert result['success'] is True
        assert result['data']['id'] == 123


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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
