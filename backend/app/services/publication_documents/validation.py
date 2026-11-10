"""HTML5 diagnostics and publication anchors; never serialize the parsed tree."""
from html.parser import HTMLParser
import re
from urllib.parse import unquote, urlsplit

import html5lib
from html5lib.constants import E as HTML_ERRORS


FORBIDDEN_TAGS = {"script", "iframe", "object", "embed", "base", "link", "meta", "style", "form",
                  "input", "button", "textarea", "select", "svg", "math"}
URL_ATTRIBUTES = {"href", "src", "action", "formaction", "poster", "xlink:href"}


class DocumentScanner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []
        self.headings = []
        self.issues = []
        self.heading = None

    def issue(self, code, message, *, blocking=False, position=None):
        line, column = position or self.getpos()
        self.issues.append({"code": code, "message": message, "line": line, "column": column + 1,
                            "severity": "error", "blocks_save": blocking})

    def handle_starttag(self, tag, attrs):
        if tag in FORBIDDEN_TAGS or "-" in tag:
            self.issue("unsafe-element", f"The <{tag}> element is not allowed in publication content.", blocking=True)
        for name, value in attrs:
            if name.startswith("on") or name in {"srcdoc", "style", "is", "srcset"}:
                self.issue("unsafe-attribute", f"The {name} attribute is not allowed.", blocking=True)
            if name in URL_ATTRIBUTES and value:
                normalized = re.sub(r"[\x00-\x20\x7f]", "", value)
                try:
                    scheme = urlsplit(normalized).scheme.lower()
                except ValueError:
                    scheme = "invalid"
                if scheme not in {"", "http", "https", "mailto", "tel"}:
                    self.issue("unsafe-url", f"Unsupported URL scheme in {name}.", blocking=True)
            if name == "id":
                if not value or value in self.ids:
                    self.issue("duplicate-id", f"Empty or duplicate anchor: {value or '(empty)'}")
                self.ids.add(value)
            if name == "href" and value:
                self.links.append((value, self.getpos()))
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.heading = {"level": int(tag[1]), "id": dict(attrs).get("id"), "title": "",
                            "line": self.getpos()[0], "column": self.getpos()[1] + 1}

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self.heading is not None:
            self.heading["title"] += data

    def handle_endtag(self, tag):
        if self.heading is not None and tag == f"h{self.heading['level']}":
            self.heading["title"] = self.heading["title"].strip()
            self.headings.append(self.heading)
            self.heading = None


def scan(content):
    scanner = DocumentScanner()
    scanner.feed(content)
    scanner.close()
    return scanner


def validate(content, *, relative_link=None):
    scanner = scan(content)
    parser = html5lib.HTMLParser(namespaceHTMLElements=False)
    parser.parseFragment(content)
    for (line, column), code, values in parser.errors:
        message = HTML_ERRORS.get(code, code)
        try:
            message = message % values
        except (KeyError, TypeError, ValueError):
            message = code
        scanner.issues.append({"code": code, "message": message, "line": line, "column": max(1, column),
                               "severity": "error", "blocks_save": False})
    for link, position in scanner.links:
        try:
            url = urlsplit(link)
        except ValueError:
            continue  # Already reported as unsafe above.
        if url.scheme or url.netloc:
            continue
        if not url.path and url.fragment:
            if unquote(url.fragment) not in scanner.ids:
                scanner.issue("missing-anchor", f"No anchor matches {link}.", position=position)
        elif url.path and not url.path.startswith("/") and relative_link:
            error = relative_link(url.path, unquote(url.fragment))
            if error:
                scanner.issue("missing-target", error, position=position)
    if not content.strip():
        scanner.issue("empty-document", "The document is empty.", position=(1, 0))
    return {"valid": not scanner.issues, "can_save": not any(i["blocks_save"] for i in scanner.issues),
            "issues": scanner.issues, "headings": scanner.headings}
