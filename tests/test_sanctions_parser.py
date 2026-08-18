"""Unit tests for sanction announcement parsers."""

import json
import unittest

from maple_reporter.sanctions.parser import (
    parse_bulletin_detail_json,
    parse_bulletin_list_json,
    parse_sanction_html_table,
)


class TestSanctionParsers(unittest.TestCase):
    def test_parse_bulletin_list_json_filtering_and_decoding(self):
        sample_payload = {
            "myDataSet": {
                "table": [
                    {
                        "Bid": 82430,
                        "Title": "新楓之谷：經典版《0817(一)遊戲異常行為制裁公告》",
                        "CreateDate": "2026/08/17 11:30:00",
                    },
                    {
                        "Bid": 82429,
                        "Title": "【伺服器維護】0817 例行維護作業公告",
                        "CreateDate": "2026/08/17 08:00:00",
                    },
                    {
                        "Bid": 82421,
                        "Title": "新楓之谷：經典版《0815(六)遊戲異常行為制裁公告》",
                        "CreateDate": "2026-08-15 09:15:20",
                    },
                ]
            }
        }
        # Encode with UTF-8-SIG (BOM)
        raw_bytes = json.dumps(sample_payload).encode("utf-8-sig")
        headers = parse_bulletin_list_json(raw_bytes)

        self.assertEqual(len(headers), 2)
        self.assertEqual(headers[0].bid, 82430)
        self.assertEqual(headers[0].publication_date, "2026-08-17")
        self.assertEqual(
            headers[0].url, "https://maplestoryclassic.beanfun.com/bulletin?Bid=82430"
        )
        self.assertEqual(headers[1].bid, 82421)
        self.assertEqual(headers[1].publication_date, "2026-08-15")

    def test_parse_sanction_html_table_three_columns_pairs(self):
        html_table = """
        <table>
            <thead>
                <tr>
                    <th>角色名稱</th>
                    <th>制裁結果</th>
                    <th>角色名稱</th>
                    <th>制裁結果</th>
                    <th>角色名稱</th>
                    <th>制裁結果</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>雲**間</td>
                    <td>永久鎖定</td>
                    <td>A**z</td>
                    <td>停權7日</td>
                    <td>測試**員</td>
                    <td>永久鎖定</td>
                </tr>
                <tr>
                    <td><span>超*神</span></td>
                    <td><b>永久鎖定</b></td>
                    <td>&nbsp;</td>
                    <td>&nbsp;</td>
                    <td></td>
                    <td></td>
                </tr>
            </tbody>
        </table>
        """
        entries = parse_sanction_html_table(html_table)
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0].masked_name, "雲**間")
        self.assertEqual(entries[0].result, "永久鎖定")
        self.assertEqual(entries[1].masked_name, "A**z")
        self.assertEqual(entries[1].result, "停權7日")
        self.assertEqual(entries[2].masked_name, "測試**員")
        self.assertEqual(entries[2].result, "永久鎖定")
        self.assertEqual(entries[3].masked_name, "超*神")
        self.assertEqual(entries[3].result, "永久鎖定")

    def test_parse_sanction_html_table_entities_and_deduplication(self):
        html_table = """
        <table>
            <tr><td>玩家&amp;測試*</td><td>警告&lt;初犯&gt;</td></tr>
            <tr><td>玩家&amp;測試*</td><td>警告&lt;初犯&gt;</td></tr>
            <tr><td>　全形空白*　</td><td>永久鎖定</td></tr>
        </table>
        """
        entries = parse_sanction_html_table(html_table)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].masked_name, "玩家&測試*")
        self.assertEqual(entries[0].result, "警告<初犯>")
        self.assertEqual(entries[1].masked_name, "全形空白*")
        self.assertEqual(entries[1].result, "永久鎖定")

    def test_parse_bulletin_detail_json_and_zero_entry_failure(self):
        valid_detail = {
            "myDataSet": {
                "table": [
                    {
                        "Bid": 82430,
                        "Title": "新楓之谷：經典版《0817(一)遊戲異常行為制裁公告》",
                        "CreateDate": "2026/08/17 12:00:00",
                        "Content": "<table><tr><td>違規*</td><td>永久封鎖</td></tr></table>",
                    }
                ]
            }
        }
        title, pub_date, url, entries = parse_bulletin_detail_json(
            json.dumps(valid_detail).encode("utf-8"), bid=82430
        )
        self.assertEqual(title, "新楓之谷：經典版《0817(一)遊戲異常行為制裁公告》")
        self.assertEqual(pub_date, "2026-08-17")
        self.assertEqual(len(entries), 1)

        empty_table_detail = {
            "myDataSet": {
                "table": [
                    {
                        "Bid": 82430,
                        "Title": "新楓之谷：經典版《0817(一)遊戲異常行為制裁公告》",
                        "CreateDate": "2026/08/17 12:00:00",
                        "Content": "<div>今日無異常名單</div>",
                    }
                ]
            }
        }
        # Title matches sanction keyword but table has 0 entries -> should raise ValueError
        with self.assertRaises(ValueError):
            parse_bulletin_detail_json(
                json.dumps(empty_table_detail).encode("utf-8"), bid=82430
            )


if __name__ == "__main__":
    unittest.main()
