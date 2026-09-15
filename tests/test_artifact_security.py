from app.services.artifacts import render_markdown, sanitize_html


def test_html_sanitizer_removes_active_content_and_unsafe_css() -> None:
    malicious = """
    <style>@import 'https://tracker.invalid/x.css'; body { color: red; }</style>
    <h1 onclick="alert(1)">Plan</h1>
    <script>fetch('https://tracker.invalid')</script>
    <form action="https://tracker.invalid"><input name="secret"></form>
    <img src="javascript:alert(1)" onerror="alert(2)">
    """
    cleaned = sanitize_html(malicious)

    assert "Content-Security-Policy" in cleaned
    assert "<script" not in cleaned
    assert "onclick" not in cleaned
    assert "onerror" not in cleaned
    assert "<form" not in cleaned
    assert "<input" not in cleaned
    assert "javascript:" not in cleaned
    assert "@import" not in cleaned


def test_html_sanitizer_keeps_only_allowlisted_stylesheet_properties() -> None:
    cleaned = sanitize_html(
        "<style>.card { color: red; position: fixed; background-color: white; }</style>"
        "<article class='card'>Safe</article>"
    )
    assert "color: red" in cleaned
    assert "background-color: white" in cleaned
    assert "position: fixed" not in cleaned


def test_markdown_is_escaped_before_rendering() -> None:
    rendered = render_markdown("# Safe\n\n<script>alert(1)</script>")
    assert "<h1>Safe</h1>" in rendered
    assert "<script" not in rendered
