"""
API 爬蟲測試
"""
import pytest
import responses

from autocrawler.api_scraper import APIScraper, scrape_api


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
