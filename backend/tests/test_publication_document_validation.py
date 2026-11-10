from app.services.publication_documents.validation import validate


def test_html5_optional_end_tags_are_valid():
    result = validate('<article><h1>Title</h1><ul><li>One<li>Two</ul><dl><dt>Word<dd>Meaning</dl></article>')
    assert result['valid']


def test_epub_attributes_and_unicode_anchors_survive_validation():
    content = '<article><h1>T</h1><a epub:type="noteref" role="doc-noteref" href="#%C4%81">1</a><p id="ā" lang="pli" translate="no">ā</p></article>'
    assert validate(content)['valid']


def test_invalid_structure_is_reported_with_source_position():
    result = validate('<article>\n<h1>Title</h1>\n<em>Unclosed</article>')
    assert not result['valid']
    assert all(issue['line'] >= 1 and issue['column'] >= 1 for issue in result['issues'])
    assert result['can_save']


def test_relative_links_are_checked_but_remote_links_are_not_fetched():
    calls = []
    result = validate('<a href="https://example.org/a#x">Remote</a><a href="preface.html#x">Local</a>',
                      relative_link=lambda path, anchor: calls.append((path, anchor)) or 'Missing target')
    assert calls == [('preface.html', 'x')]
    assert any(issue['code'] == 'missing-target' for issue in result['issues'])
