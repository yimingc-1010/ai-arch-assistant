"""
HTML 爬蟲測試
"""
import pytest
import responses

from autocrawler.html_scraper import HTMLScraper, scrape_html


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
