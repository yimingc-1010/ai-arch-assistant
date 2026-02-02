"""
自動爬蟲主程式
自動判斷最佳爬取策略並輸出 JSON 格式
"""
import json
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime

from url_analyzer import URLAnalyzer
from html_scraper import HTMLScraper
from api_scraper import APIScraper
from law_scraper import get_law_scraper


class AutoCrawler:
    """
    自動爬蟲
    根據 URL 自動選擇最佳爬取策略 (HTML 解析或 API Fetch)
    """

    def __init__(self, verbose: bool = False):
        self.analyzer = URLAnalyzer()
        self.html_scraper = HTMLScraper()
        self.api_scraper = APIScraper()
        self.verbose = verbose

    def crawl(self, url: str, force_strategy: Optional[str] = None,
              extract_config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        爬取指定 URL

        Args:
            url: 目標 URL
            force_strategy: 強制使用的策略 ('html' 或 'api')
            extract_config: 自定義提取配置

        Returns:
            Dict containing crawled data in JSON format
        """
        result = {
            'url': url,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'strategy_analysis': None,
            'strategy_used': None,
            'success': False,
            'data': None,
            'error': None,
        }

        # 分析 URL
        if force_strategy:
            result['strategy_used'] = force_strategy
            result['strategy_analysis'] = {'forced': True}
        else:
            analysis = self.analyzer.analyze(url)
            result['strategy_analysis'] = analysis
            result['strategy_used'] = analysis['strategy']

            if self.verbose:
                print(f"[INFO] URL: {url}")
                print(f"[INFO] Strategy: {analysis['strategy']} (confidence: {analysis['confidence']:.2f})")
                for reason in analysis['reasons']:
                    print(f"[INFO]   - {reason}")

        # 執行爬取
        try:
            if result['strategy_used'] in ('law_moj', 'law_arkiteki'):
                law_scraper = get_law_scraper(url)
                if law_scraper:
                    crawl_result = law_scraper.scrape(url)
                else:
                    crawl_result = self.html_scraper.scrape(url, extract_config)
            elif result['strategy_used'] == 'api':
                crawl_result = self.api_scraper.scrape(url, extract_config)
            else:
                crawl_result = self.html_scraper.scrape(url, extract_config)

            result['success'] = crawl_result.get('success', False)
            result['data'] = crawl_result.get('data')
            result['error'] = crawl_result.get('error')

            # 如果 API 策略失敗，嘗試 HTML 策略
            if not result['success'] and result['strategy_used'] == 'api':
                if self.verbose:
                    print("[INFO] API strategy failed, trying HTML strategy...")

                result['strategy_used'] = 'html_fallback'
                crawl_result = self.html_scraper.scrape(url, extract_config)
                result['success'] = crawl_result.get('success', False)
                result['data'] = crawl_result.get('data')
                result['error'] = crawl_result.get('error')

        except Exception as e:
            result['error'] = str(e)

        return result

    def crawl_multiple(self, urls: List[str], **kwargs) -> List[Dict[str, Any]]:
        """
        爬取多個 URL

        Args:
            urls: URL 列表
            **kwargs: 傳遞給 crawl() 的參數

        Returns:
            List of crawl results
        """
        results = []
        for i, url in enumerate(urls):
            if self.verbose:
                print(f"\n[INFO] Processing {i+1}/{len(urls)}: {url}")

            result = self.crawl(url, **kwargs)
            results.append(result)

        return results

    def to_json(self, data: Any, pretty: bool = True) -> str:
        """
        將資料轉換為 JSON 字串

        Args:
            data: 要轉換的資料
            pretty: 是否美化輸出

        Returns:
            JSON 字串
        """
        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        return json.dumps(data, ensure_ascii=False, default=str)

    def save_json(self, data: Any, filepath: str, pretty: bool = True) -> None:
        """
        將資料儲存為 JSON 檔案

        Args:
            data: 要儲存的資料
            filepath: 檔案路徑
            pretty: 是否美化輸出
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2 if pretty else None, default=str)


def crawl(url: str, **kwargs) -> Dict[str, Any]:
    """便利函數：爬取單一 URL"""
    crawler = AutoCrawler()
    return crawler.crawl(url, **kwargs)


def main():
    """命令列介面"""
    import argparse

    parser = argparse.ArgumentParser(
        description='自動爬蟲 - 自動選擇最佳爬取策略'
    )
    parser.add_argument('url', help='要爬取的 URL')
    parser.add_argument(
        '-s', '--strategy',
        choices=['html', 'api'],
        help='強制使用的策略'
    )
    parser.add_argument(
        '-o', '--output',
        help='輸出檔案路徑'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='顯示詳細資訊'
    )
    parser.add_argument(
        '--compact',
        action='store_true',
        help='緊湊的 JSON 輸出'
    )
    parser.add_argument(
        '--csv',
        action='store_true',
        help='輸出 CSV 格式 (僅適用於法規爬取)'
    )

    args = parser.parse_args()

    crawler = AutoCrawler(verbose=args.verbose)
    result = crawler.crawl(args.url, force_strategy=args.strategy)

    # CSV 輸出 (僅適用於法規)
    if args.csv:
        if result['success'] and result['strategy_used'] in ('law_moj', 'law_arkiteki'):
            from law_exporter import export_csv
            csv_output = export_csv(result['data'])
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(csv_output)
                if args.verbose:
                    print(f"\n[INFO] CSV saved to: {args.output}")
            else:
                print(csv_output)
        else:
            print("[ERROR] CSV output is only available for law scraping results", file=sys.stderr)
            sys.exit(1)
    else:
        json_output = crawler.to_json(result, pretty=not args.compact)

        if args.output:
            crawler.save_json(result, args.output, pretty=not args.compact)
            if args.verbose:
                print(f"\n[INFO] Result saved to: {args.output}")
        else:
            print(json_output)


if __name__ == '__main__':
    main()
