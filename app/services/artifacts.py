import re

import bleach
import mistune
import tinycss2
from bleach.css_sanitizer import CSSSanitizer

ALLOWED_TAGS = {
    "a",
    "article",
    "aside",
    "blockquote",
    "br",
    "caption",
    "code",
    "col",
    "colgroup",
    "dd",
    "del",
    "details",
    "div",
    "dl",
    "dt",
    "em",
    "figcaption",
    "figure",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "header",
    "hr",
    "li",
    "main",
    "mark",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "small",
    "span",
    "strong",
    "style",
    "sub",
    "summary",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}

ALLOWED_ATTRIBUTES = {
    "*": ["class", "id", "title", "aria-label", "aria-hidden", "role", "style"],
    "a": ["title"],
    "ol": ["start"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan", "scope"],
    "col": ["span"],
}

ALLOWED_CSS_PROPERTIES = [
    "align-items",
    "background",
    "background-color",
    "border",
    "border-bottom",
    "border-color",
    "border-left",
    "border-radius",
    "border-right",
    "border-top",
    "box-shadow",
    "color",
    "display",
    "flex",
    "flex-basis",
    "flex-direction",
    "flex-grow",
    "flex-wrap",
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "gap",
    "grid-template-columns",
    "height",
    "justify-content",
    "letter-spacing",
    "line-height",
    "list-style",
    "margin",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-top",
    "max-width",
    "min-height",
    "opacity",
    "overflow",
    "padding",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "text-align",
    "text-decoration",
    "text-transform",
    "width",
]

CSS_SANITIZER = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)
MARKDOWN = mistune.create_markdown(escape=True)
FENCE_RE = re.compile(r"^\s*```(?:html|markdown|md)?\s*(.*?)\s*```\s*$", re.I | re.S)
STYLE_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.I | re.S)
UNSAFE_CSS_RE = re.compile(
    r"@import|@font-face|url\s*\(|expression\s*\(|javascript\s*:|behavior\s*:|-moz-binding",
    re.I,
)

VIEWER_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'none'; style-src 'unsafe-inline'; font-src 'none'; media-src 'none'; connect-src 'none'; frame-src 'none'; object-src 'none'; form-action 'none'; base-uri 'none'">
<style>
:root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
body { margin: 0; padding: 32px; color: #17211b; background: #fffef8; line-height: 1.6; }
pre { overflow: auto; padding: 16px; background: #f2f3ed; border-radius: 10px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #d9ddd5; padding: 8px 10px; text-align: left; }
a { color: #126a45; }
</style>
{styles}
</head>
<body>{body}</body>
</html>"""


def strip_code_fence(source: str) -> str:
    match = FENCE_RE.match(source)
    return match.group(1).strip() if match else source.strip()


def _sanitize_stylesheet(css: str) -> str:
    if UNSAFE_CSS_RE.search(css) or "</" in css:
        return ""
    safe_rules: list[str] = []
    for rule in tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True):
        if rule.type != "qualified-rule":
            continue
        selector = tinycss2.serialize(rule.prelude).strip()
        if not selector or "@" in selector or "</" in selector:
            continue
        declarations: list[str] = []
        for declaration in tinycss2.parse_declaration_list(
            rule.content, skip_comments=True, skip_whitespace=True
        ):
            if declaration.type != "declaration":
                continue
            name = declaration.lower_name
            value = tinycss2.serialize(declaration.value).strip()
            if name in ALLOWED_CSS_PROPERTIES and value and not UNSAFE_CSS_RE.search(value):
                important = " !important" if declaration.important else ""
                declarations.append(f"{name}: {value}{important}")
        if declarations:
            safe_rules.append(f"{selector} {{ {'; '.join(declarations)} }}")
    return "\n".join(safe_rules)


def _safe_styles(source: str) -> tuple[str, str]:
    styles: list[str] = []

    def collect(match: re.Match[str]) -> str:
        css = _sanitize_stylesheet(match.group(1))
        if css:
            styles.append(css)
        return ""

    return STYLE_RE.sub(collect, source), "\n".join(f"<style>{css}</style>" for css in styles)


def sanitize_html(source: str) -> str:
    source = strip_code_fence(source)
    without_styles, safe_styles = _safe_styles(source)
    body = bleach.clean(
        without_styles,
        tags=ALLOWED_TAGS - {"style"},
        attributes=ALLOWED_ATTRIBUTES,
        protocols=set(),
        css_sanitizer=CSS_SANITIZER,
        strip=True,
        strip_comments=True,
    )
    return VIEWER_SHELL.replace("{styles}", safe_styles).replace("{body}", body)


def render_markdown(source: str) -> str:
    source = strip_code_fence(source)
    rendered = MARKDOWN(source)
    return sanitize_html(rendered)


def render_artifact(kind: str, source: str) -> str:
    return render_markdown(source) if kind == "markdown" else sanitize_html(source)
