"""Regression coverage for legacy pairs and names-only sanction tables."""

import json

import pytest

from maple_reporter.sanctions.matcher import find_matching_bulletin
from maple_reporter.sanctions.models import BulletinDetail
from maple_reporter.sanctions.parser import parse_bulletin_detail_json, parse_sanction_html_table


def test_names_only_detail_matches_target_in_even_column():
    content = (
        '<p>以下帳號已執行「永久鎖定」處分。</p>'
        '<table><tr><td colspan="6">角色名稱</td></tr>'
        '<tr><td>sample1</td><td>sample2</td><td>sample3</td>'
        '<td>T***ID</td><td>sample5</td><td>sample6</td></tr></table>'
    )
    payload = {'data': {'myDataSet': {'table': {
        'title': '遊戲異常行為制裁公告', 'startDate': '2026/09/07', 'content': content,
    }}}}
    title, date, url, entries = parse_bulletin_detail_json(json.dumps(payload).encode(), bid=100)
    assert len(entries) == 6
    assert all(entry.result == '永久鎖定' for entry in entries)
    bulletin = BulletinDetail(100, date, title, url, '', tuple(entries))
    match = find_matching_bulletin('TestID', '2026-09-07', [bulletin])
    assert match is not None
    assert match.entry.masked_name == 'T***ID'
    assert match.entry.result == '永久鎖定'


def test_duration_punishment():
    entries = parse_sanction_html_table(
        '<p>已執行「停權7天」處分。</p><table><tr><th>角色名稱</th></tr><tr><td>player</td></tr></table>'
    )
    assert entries[0].result == '停權7天'


def test_conflicting_punishment_fails():
    with pytest.raises(ValueError, match='punishment'):
        parse_sanction_html_table(
            '<p>已執行「永久停權」處分。</p><p>已執行「停權7天」處分。</p>'
            '<table><tr><th>角色名稱</th></tr><tr><td>player</td></tr></table>'
        )


@pytest.mark.parametrize('count', [1, 3, 6])
def test_names_only_width_and_empty_cells(count):
    cells = ''.join(f'<td>player{i}</td>' for i in range(count))
    entries = parse_sanction_html_table(
        f'<p>已執行「永久停權」處分。</p><table><tr><th colspan="6">角色名稱</th></tr>'
        f'<tr>{cells}<td>&nbsp;</td></tr></table>'
    )
    assert [(e.masked_name, e.result) for e in entries] == [(f'player{i}', '永久停權') for i in range(count)]


def test_each_table_uses_its_own_schema():
    entries = parse_sanction_html_table(
        '<p>已執行「永久鎖定」處分。</p>'
        '<table><tr><td>角色名稱</td><td>處置結果</td></tr><tr><td>old*</td><td>停權7天</td></tr></table>'
        '<table><tr><th>角色名稱</th><th>角色名稱</th></tr><tr><td>new1</td><td>new2</td></tr></table>'
    )
    assert [(e.masked_name, e.result) for e in entries] == [('old*', '停權7天'), ('new1', '永久鎖定'), ('new2', '永久鎖定')]


def test_names_only_missing_punishment_fails():
    with pytest.raises(ValueError, match='punishment'):
        parse_sanction_html_table('<table><tr><th>角色名稱</th></tr><tr><td>player</td></tr></table>')


@pytest.mark.parametrize('name', ['處置', '懲處', '角色名稱'])
def test_header_keyword_in_player_name_does_not_change_schema(name):
    entries = parse_sanction_html_table(
        '<p>已執行「永久鎖定」處分。</p>'
        f'<table><tr><td colspan="6">角色名稱</td></tr><tr><td>sample</td><td>{name}</td></tr></table>'
    )
    assert [(e.masked_name, e.result) for e in entries] == [('sample', '永久鎖定'), (name, '永久鎖定')]


@pytest.mark.parametrize('text, expected', [
    ('已進行『永久鎖定』處分。', '永久鎖定'),
    ('已執行永久鎖定。', '永久鎖定'),
    ('予以「停權七天」處分。', '停權七天'),
])
def test_explicit_punishment_wording_variants(text, expected):
    entries = parse_sanction_html_table(
        f'<p>{text}</p><table><tr><th>角色名稱</th></tr><tr><td>sample</td></tr></table>'
    )
    assert entries[0].result == expected


@pytest.mark.parametrize('text', ['可能已執行永久鎖定。', '尚未執行永久鎖定。', '已執行永久鎖定解除處分。'])
def test_uncertain_or_negated_punishment_is_rejected(text):
    with pytest.raises(ValueError, match='punishment'):
        parse_sanction_html_table(
            f'<p>{text}</p><table><tr><th>角色名稱</th></tr><tr><td>sample</td></tr></table>'
        )
