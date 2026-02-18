"""命令列介面"""
import argparse
import json
import sys

from autocrawler.crawler import AutoCrawler


# Try to load the law plugin if installed
try:
    from autocrawler_law import plugin
    plugin.register_law_strategies()

    from autocrawler_law.scrapers import get_law_scraper

    def _law_scraper_factory(url):
        return get_law_scraper(url)

    _LAW_AVAILABLE = True
except ImportError:
    _LAW_AVAILABLE = False


def main():
    """命令列介面"""
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

    # Register law scrapers if available
    if _LAW_AVAILABLE:
        crawler.register_scraper('law_moj', _law_scraper_factory)
        crawler.register_scraper('law_arkiteki', _law_scraper_factory)

    result = crawler.crawl(args.url, force_strategy=args.strategy)

    # CSV 輸出 (僅適用於法規)
    if args.csv:
        if not _LAW_AVAILABLE:
            print("[ERROR] CSV output requires autocrawler-law package. "
                  "Install with: pip install autocrawler-cli[law]", file=sys.stderr)
            sys.exit(1)

        if result['success'] and result['strategy_used'] in ('law_moj', 'law_arkiteki'):
            from autocrawler_law.exporter import export_csv
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
