import re

from app.models.schemas import GenerationMode

ESSAY_PATTERN = re.compile(r"\b(ship\s*30|essay|long[- ]form|~?1[,.]?250\s+words?)\b", re.I)
HTML_PATTERN = re.compile(r"\b(html|webpage|landing page|interactive artifact|html/css)\b", re.I)
MARKDOWN_PATTERN = re.compile(r"\b(markdown|\.md|memo|brief|document|playbook)\b", re.I)


def route_mode(content: str, requested: GenerationMode) -> GenerationMode:
    if requested != GenerationMode.AUTO:
        return requested
    if ESSAY_PATTERN.search(content):
        return GenerationMode.ESSAY
    if HTML_PATTERN.search(content):
        return GenerationMode.HTML
    if MARKDOWN_PATTERN.search(content) and re.search(
        r"\b(create|write|draft|generate|turn)\b", content, re.I
    ):
        return GenerationMode.MARKDOWN
    return GenerationMode.ANSWER
