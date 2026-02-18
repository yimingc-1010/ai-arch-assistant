"""
法規輸出模組測試
"""
import pytest

from autocrawler_law.exporter import export_csv, export_detailed_csv


class TestLawExporter:
    """法規輸出模組測試"""

    def test_basic_csv_export(self):
        """測試基本 CSV 輸出"""
        law_data = {
            'law_name': '建築法',
            'articles': [
                {
                    'number': '第 1 條',
                    'chapter': '第 一 章 總則',
                    'content': '為實施建築管理。',
                    'items': None,
                },
                {
                    'number': '第 2 條',
                    'chapter': '第 一 章 總則',
                    'content': '主管建築機關。',
                    'items': None,
                },
            ]
        }

        csv_output = export_csv(law_data)

        assert '條號' in csv_output
        assert '章節' in csv_output
        assert '條文內容' in csv_output
        assert '第 1 條' in csv_output
        assert '第 一 章 總則' in csv_output
        assert '建築管理' in csv_output

    def test_csv_with_items(self):
        """測試帶有項目的 CSV 輸出"""
        law_data = {
            'law_name': '建築法',
            'articles': [
                {
                    'number': '第 3 條',
                    'chapter': '第 一 章 總則',
                    'content': '本法用詞定義如下：',
                    'items': ['一、建築物：定著於土地。', '二、雜項工作物：其他。'],
                },
            ]
        }

        csv_output = export_csv(law_data)

        assert '第 3 條' in csv_output
        assert '一、建築物' in csv_output
        assert '二、雜項工作物' in csv_output

    def test_detailed_csv_export(self):
        """測試詳細 CSV 輸出"""
        law_data = {
            'law_name': '建築法',
            'articles': [
                {
                    'number': '第 1 條',
                    'chapter': '第 一 章',
                    'content': '測試內容。',
                    'items': ['一、項目一', '二、項目二'],
                },
            ]
        }

        csv_output = export_detailed_csv(law_data)

        assert '法規名稱' in csv_output
        assert '項目數' in csv_output
        assert '建築法' in csv_output

    def test_empty_articles(self):
        """測試空條文列表"""
        law_data = {
            'law_name': '空法',
            'articles': []
        }

        csv_output = export_csv(law_data)

        # 應該只有標題行
        lines = csv_output.strip().split('\n')
        assert len(lines) == 1
        assert '條號' in lines[0]
