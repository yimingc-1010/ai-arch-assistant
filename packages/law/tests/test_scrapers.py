"""
法規爬蟲測試
"""
import pytest
import responses
from unittest.mock import patch, MagicMock

from autocrawler_law.scrapers import (
    LawScraper, MojLawScraper, ArkitekiScraper,
    get_law_scraper, scrape_law
)
from autocrawler_law.plugin import detect_law_site


class TestMojLawScraper:
    """全國法規資料庫爬蟲測試"""

    @responses.activate
    def test_basic_law_extraction(self):
        """測試基本法規提取"""
        url = 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109'
        html_content = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>建築法-全國法規資料庫</title>
        </head>
        <body>
            <div class="law-reg-content">
                <div class="h3 char-2">第 一 章 總則</div>
                <div class="row">
                    <div class="col-no"><a name="1">第 1 條</a></div>
                    <div class="col-data">
                        <div class="law-article">
                            <div class="line-0000">為實施建築管理，以維護公共安全、公共交通、公共衛生及增進市容觀瞻，特制定本法。</div>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-no"><a name="2">第 2 條</a></div>
                    <div class="col-data">
                        <div class="law-article">
                            <div class="line-0000">主管建築機關，在中央為內政部。</div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        '''

        responses.add(responses.GET, url, body=html_content, status=200,
                      content_type='text/html; charset=utf-8')

        scraper = MojLawScraper()
        result = scraper.scrape(url)

        assert result['success'] is True
        assert result['data']['source'] == 'law.moj.gov.tw'
        assert result['data']['pcode'] == 'D0070109'
        assert '建築法' in result['data']['law_name']
        assert len(result['data']['articles']) >= 2
        assert result['data']['articles'][0]['number'] == '第 1 條'
        assert '建築管理' in result['data']['articles'][0]['content']

    @responses.activate
    def test_chapter_extraction(self):
        """測試章節提取"""
        url = 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=TEST001'
        html_content = '''
        <html>
        <head><title>測試法-全國法規資料庫</title></head>
        <body>
            <div class="law-reg-content">
                <div class="h3 char-2">第 一 章 總則</div>
                <div class="h3 char-2">第 二 章 建築許可</div>
                <div class="h3 char-2">第 三 章 建築基地</div>
            </div>
        </body>
        </html>
        '''

        responses.add(responses.GET, url, body=html_content, status=200)

        scraper = MojLawScraper()
        result = scraper.scrape(url)

        assert result['success'] is True
        assert len(result['data']['chapters']) == 3
        assert result['data']['chapters'][0]['number'] == '第 一 章'
        assert result['data']['chapters'][0]['title'] == '總則'

    @responses.activate
    def test_article_with_items(self):
        """測試帶有項目的條文提取"""
        url = 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=TEST002'
        html_content = '''
        <html>
        <head><title>測試法</title></head>
        <body>
            <div class="law-reg-content">
                <div class="row">
                    <div class="col-no">第 3 條</div>
                    <div class="col-data">
                        <div class="law-article">
                            <div class="line-0000">本法用詞定義如下：</div>
                            <div class="line-0001">一、建築物：定著於土地上之工作物。</div>
                            <div class="line-0002">二、雜項工作物：其他工作物。</div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        '''

        responses.add(responses.GET, url, body=html_content, status=200)

        scraper = MojLawScraper()
        result = scraper.scrape(url)

        assert result['success'] is True
        assert len(result['data']['articles']) >= 1

    @responses.activate
    def test_last_modified_extraction(self):
        """測試修正日期提取"""
        url = 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=TEST003'
        html_content = '''
        <html>
        <head><title>測試法</title></head>
        <body>
            <div>修正日期：民國 111 年 05 月 11 日</div>
        </body>
        </html>
        '''

        responses.add(responses.GET, url, body=html_content, status=200)

        scraper = MojLawScraper()
        result = scraper.scrape(url)

        assert result['success'] is True
        assert result['data']['last_modified'] is not None
        assert '111' in result['data']['last_modified']

    @responses.activate
    def test_network_error_handling(self):
        """測試網路錯誤處理"""
        url = 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=ERROR'

        responses.add(responses.GET, url, body=Exception('Connection error'))

        scraper = MojLawScraper()
        result = scraper.scrape(url)

        assert result['success'] is False
        assert result['error'] is not None


class TestArkitekiScraper:
    """ArkiTeki 爬蟲測試"""

    @responses.activate
    def test_basic_arkiteki_extraction(self):
        """測試基本 ArkiTeki 法規提取"""
        url = 'https://arkiteki.com/term/總則編'
        html_content = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>建築技術規則總則編 | ArkiTeki</title>
        </head>
        <body>
            <h1>建築技術規則總則編</h1>
            <table class="law-table">
                <tr class="first-law-no">
                    <td class="law-no">第 1 條</td>
                    <td class="law-content" data-compound-no="第 1 條">
                        本規則依建築法第九十七條規定訂定之。
                    </td>
                </tr>
                <tr>
                    <td class="law-no">第 2 條</td>
                    <td class="law-content" data-compound-no="第 2 條">
                        建築物之設計、施工、構造及設備，依本規則之規定。
                    </td>
                </tr>
            </table>
        </body>
        </html>
        '''

        responses.add(responses.GET, url, body=html_content, status=200,
                      content_type='text/html; charset=utf-8')

        scraper = ArkitekiScraper()
        result = scraper.scrape(url)

        assert result['success'] is True
        assert result['data']['source'] == 'arkiteki.com'
        assert '總則編' in result['data']['law_name']
        assert len(result['data']['articles']) == 2
        assert result['data']['articles'][0]['number'] == '第 1 條'
        assert '建築法' in result['data']['articles'][0]['content']

    @responses.activate
    def test_arkiteki_chapter_handling(self):
        """測試 ArkiTeki 章節處理"""
        url = 'https://arkiteki.com/term/test'
        html_content = '''
        <html>
        <head><title>測試規則 | ArkiTeki</title></head>
        <body>
            <h1>測試規則</h1>
            <table class="law-table">
                <tr class="chapter">
                    <th colspan="2">第 一 章 總則</th>
                </tr>
                <tr>
                    <td class="law-no">第 1 條</td>
                    <td class="law-content">本規則之適用範圍。</td>
                </tr>
                <tr class="chapter">
                    <th colspan="2">第 二 章 設計</th>
                </tr>
                <tr>
                    <td class="law-no">第 10 條</td>
                    <td class="law-content">設計相關規定。</td>
                </tr>
            </table>
        </body>
        </html>
        '''

        responses.add(responses.GET, url, body=html_content, status=200)

        scraper = ArkitekiScraper()
        result = scraper.scrape(url)

        assert result['success'] is True
        assert len(result['data']['chapters']) >= 2

    @responses.activate
    def test_arkiteki_network_error(self):
        """測試 ArkiTeki 網路錯誤處理"""
        url = 'https://arkiteki.com/term/error'

        responses.add(responses.GET, url, body=Exception('Network error'))

        scraper = ArkitekiScraper()
        result = scraper.scrape(url)

        assert result['success'] is False
        assert 'error' in result


class TestGetLawScraper:
    """get_law_scraper 函數測試"""

    def test_moj_scraper_selection(self):
        """測試全國法規資料庫爬蟲選擇"""
        url = 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109'
        scraper = get_law_scraper(url)

        assert scraper is not None
        assert isinstance(scraper, MojLawScraper)

    def test_arkiteki_scraper_selection(self):
        """測試 ArkiTeki 爬蟲選擇"""
        url = 'https://arkiteki.com/term/總則編'
        scraper = get_law_scraper(url)

        assert scraper is not None
        assert isinstance(scraper, ArkitekiScraper)

    def test_unknown_site_returns_none(self):
        """測試未知網站返回 None"""
        url = 'https://unknown-law-site.com/law/123'
        scraper = get_law_scraper(url)

        assert scraper is None

    def test_scrape_law_convenience_function(self):
        """測試 scrape_law 便利函數"""
        url = 'https://unknown.com/law'
        result = scrape_law(url)

        assert result['success'] is False
        assert 'Unsupported' in result['error']


class TestLawSiteDetection:
    """Law site URL detection tests"""

    def test_moj_law_detection(self):
        """測試全國法規資料庫偵測"""
        url = 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109'
        result = detect_law_site(url)
        assert result == 'law_moj'

    def test_arkiteki_term_detection(self):
        """測試 ArkiTeki term 頁面偵測"""
        url = 'https://arkiteki.com/term/總則編'
        result = detect_law_site(url)
        assert result == 'law_arkiteki'

    def test_arkiteki_non_term_not_detected(self):
        """測試 ArkiTeki 非 term 頁面不被偵測為法規"""
        url = 'https://arkiteki.com/about'
        result = detect_law_site(url)
        assert result is None


class TestIntegration:
    """整合測試"""

    @responses.activate
    def test_full_moj_workflow(self):
        """測試完整的全國法規資料庫工作流程"""
        from autocrawler_law.exporter import export_csv

        url = 'https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0070109'
        html_content = '''
        <html>
        <head><title>建築法-全國法規資料庫</title></head>
        <body>
            <div>修正日期：民國 111 年 05 月 11 日</div>
            <div class="law-reg-content">
                <div class="h3 char-2">第 一 章 總則</div>
                <div class="row">
                    <div class="col-no">第 1 條</div>
                    <div class="col-data">
                        <div class="law-article">
                            <div>為實施建築管理，特制定本法。</div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        '''

        responses.add(responses.GET, url, body=html_content, status=200)

        # 1. 爬取
        result = scrape_law(url)
        assert result['success'] is True

        # 2. 輸出 CSV
        csv_output = export_csv(result['data'])
        assert '第 1 條' in csv_output
        assert '建築管理' in csv_output
