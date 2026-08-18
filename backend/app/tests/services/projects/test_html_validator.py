from app.services.projects.html_validator import validate_bilara_html


def test_accepts_balanced_markup_spanning_segments():
    result = validate_bilara_html(
        {
            "mn1:1.1": "<section><p>{}</p>",
            "mn1:1.2": "<p>{}</p></section>",
        }
    )

    assert result.valid is True
    assert result.errors == []
    assert result.checked_segments == 2


def test_reports_mismatched_closing_tag_at_the_segment_that_contains_it():
    result = validate_bilara_html(
        {
            "mn1:1.1": "<section><p>{}",
            "mn1:1.2": "</section><p>{}</p>",
        }
    )

    assert result.valid is False
    assert [(issue.code, issue.uid, issue.related_uid) for issue in result.errors] == [
        ("mismatched-closing-tag", "mn1:1.2", "mn1:1.1")
    ]
    assert result.errors[0].offset == 0


def test_requires_one_text_placeholder_in_every_segment():
    result = validate_bilara_html({"mn1:1.1": "<p></p>"})

    assert result.valid is False
    assert [(issue.code, issue.uid) for issue in result.errors] == [
        ("invalid-placeholder-count", "mn1:1.1")
    ]


def test_rejects_executable_markup_and_event_attributes():
    result = validate_bilara_html(
        {"mn1:1.1": "<p onclick='run()'>{}</p><script>alert(1)</script>"}
    )

    assert result.valid is False
    assert {issue.code for issue in result.errors} == {
        "forbidden-attribute",
        "forbidden-tag",
    }


def test_accepts_void_and_explicitly_self_closing_elements():
    result = validate_bilara_html(
        {"mn1:1.1": "<div><br/>{}<span class='line' /></div>"}
    )

    assert result.valid is True


def test_reports_malformed_tag_syntax_instead_of_silently_accepting_it():
    result = validate_bilara_html({"mn1:1.1": '<p class="broken>{}</p>'})

    assert result.valid is False
    assert [(issue.code, issue.uid) for issue in result.errors] == [
        ("malformed-html", "mn1:1.1")
    ]


def test_rejects_duplicate_attributes_on_the_same_element():
    result = validate_bilara_html(
        {"mn1:1.1": "<span class='verse' class='gatha'>{}</span>"}
    )

    assert result.valid is False
    assert [issue.code for issue in result.errors] == ["duplicate-attribute"]


def test_rejects_unknown_named_character_references():
    result = validate_bilara_html({"mn1:1.1": "<p>{}&notARealEntity;</p>"})

    assert result.valid is False
    assert [issue.code for issue in result.errors] == ["unknown-entity"]
