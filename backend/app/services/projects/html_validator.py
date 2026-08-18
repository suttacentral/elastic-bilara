from dataclasses import dataclass, field
from html.entities import html5
from html.parser import HTMLParser


VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
FORBIDDEN_ELEMENTS = {"base", "embed", "iframe", "link", "meta", "object", "script"}
URL_ATTRIBUTES = {"action", "formaction", "href", "poster", "src", "xlink:href"}


@dataclass(frozen=True)
class HtmlValidationIssue:
    severity: str
    code: str
    uid: str
    offset: int
    message: str
    related_uid: str | None = None


@dataclass(frozen=True)
class HtmlValidationResult:
    valid: bool
    checked_segments: int
    errors: list[HtmlValidationIssue] = field(default_factory=list)
    warnings: list[HtmlValidationIssue] = field(default_factory=list)


class _BilaraHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[tuple[str, str, int]] = []
        self.current_uid = ""
        self.segment_start_line = 1
        self.segment_start_column = 0
        self.segment_line_offsets = [0]
        self.errors: list[HtmlValidationIssue] = []

    def begin_segment(self, uid: str, markup: str) -> None:
        self.current_uid = uid
        self.segment_start_line = self.lineno
        self.segment_start_column = self.offset
        self.segment_line_offsets = [0]
        for index, character in enumerate(markup):
            if character == "\n":
                self.segment_line_offsets.append(index + 1)

    def _segment_offset(self) -> int:
        line, column = self.getpos()
        relative_line = max(0, line - self.segment_start_line)
        if relative_line == 0:
            return max(0, column - self.segment_start_column)
        if relative_line >= len(self.segment_line_offsets):
            return self.segment_line_offsets[-1]
        return self.segment_line_offsets[relative_line] + column

    def _validate_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in FORBIDDEN_ELEMENTS:
            self.errors.append(
                HtmlValidationIssue(
                    severity="error",
                    code="forbidden-tag",
                    uid=self.current_uid,
                    offset=self._segment_offset(),
                    message=f"Forbidden <{tag}> tag",
                )
            )
        seen_attributes: set[str] = set()
        for name, value in attrs:
            normalized_name = name.lower()
            normalized_value = (value or "").strip().lower()
            if normalized_name in seen_attributes:
                self.errors.append(
                    HtmlValidationIssue(
                        severity="error",
                        code="duplicate-attribute",
                        uid=self.current_uid,
                        offset=self._segment_offset(),
                        message=f"Duplicate {name} attribute on <{tag}>",
                    )
                )
            seen_attributes.add(normalized_name)
            if normalized_name.startswith("on") or normalized_name == "srcdoc":
                self.errors.append(
                    HtmlValidationIssue(
                        severity="error",
                        code="forbidden-attribute",
                        uid=self.current_uid,
                        offset=self._segment_offset(),
                        message=f"Forbidden {name} attribute on <{tag}>",
                    )
                )
            elif normalized_name in URL_ATTRIBUTES and normalized_value.startswith(
                ("javascript:", "data:", "vbscript:")
            ):
                self.errors.append(
                    HtmlValidationIssue(
                        severity="error",
                        code="unsafe-url",
                        uid=self.current_uid,
                        offset=self._segment_offset(),
                        message=f"Unsafe URL in {name} attribute on <{tag}>",
                    )
                )
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._validate_tag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.stack.append((tag, self.current_uid, self._segment_offset()))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._validate_tag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
            return

        matching_index = next(
            (index for index in range(len(self.stack) - 1, -1, -1) if self.stack[index][0] == tag),
            None,
        )
        if matching_index is not None:
            expected_tag, opening_uid, _ = self.stack[-1]
            self.errors.append(
                HtmlValidationIssue(
                    severity="error",
                    code="mismatched-closing-tag",
                    uid=self.current_uid,
                    offset=self._segment_offset(),
                    message=f"Expected </{expected_tag}>, found </{tag}>",
                    related_uid=opening_uid,
                )
            )
            del self.stack[matching_index:]
            return

        self.errors.append(
            HtmlValidationIssue(
                severity="error",
                code="unexpected-closing-tag",
                uid=self.current_uid,
                offset=self._segment_offset(),
                message=f"Unexpected closing tag </{tag}>",
            )
        )

    def handle_entityref(self, name: str) -> None:
        if name not in html5 and f"{name};" not in html5:
            self.errors.append(
                HtmlValidationIssue(
                    severity="error",
                    code="unknown-entity",
                    uid=self.current_uid,
                    offset=self._segment_offset(),
                    message=f"Unknown character reference &{name};",
                )
            )


def validate_bilara_html(segments: dict[str, str]) -> HtmlValidationResult:
    parser = _BilaraHtmlParser()
    for uid, markup in segments.items():
        parser.begin_segment(uid, markup)
        placeholder_count = markup.count("{}")
        if placeholder_count != 1:
            parser.errors.append(
                HtmlValidationIssue(
                    severity="error",
                    code="invalid-placeholder-count",
                    uid=uid,
                    offset=markup.find("{}", markup.find("{}") + 2) if placeholder_count > 1 else 0,
                    message=f"Expected exactly one {{}} placeholder, found {placeholder_count}",
                )
            )
        parser.feed(markup)
        if parser.rawdata:
            malformed_offset = max(0, len(markup) - len(parser.rawdata))
            parser.errors.append(
                HtmlValidationIssue(
                    severity="error",
                    code="malformed-html",
                    uid=uid,
                    offset=malformed_offset,
                    message="Malformed or incomplete HTML tag",
                )
            )
            parser.rawdata = ""
    parser.close()
    for tag, opening_uid, opening_offset in reversed(parser.stack):
        parser.errors.append(
            HtmlValidationIssue(
                severity="error",
                code="unclosed-tag",
                uid=opening_uid,
                offset=opening_offset,
                message=f"Unclosed <{tag}> tag",
            )
        )
    return HtmlValidationResult(
        valid=not parser.errors,
        checked_segments=len(segments),
        errors=parser.errors,
    )
