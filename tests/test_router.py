import pytest

from app.models.schemas import GenerationMode
from app.services.router import route_mode


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("How do teams improve retention?", GenerationMode.ANSWER),
        ("Write a Ship 30 for 30 essay about retention", GenerationMode.ESSAY),
        ("Create an HTML briefing card", GenerationMode.HTML),
        ("Draft a markdown playbook", GenerationMode.MARKDOWN),
    ],
)
def test_auto_route_is_deterministic(prompt: str, expected: GenerationMode) -> None:
    assert route_mode(prompt, GenerationMode.AUTO) == expected


def test_explicit_mode_wins_over_heuristic() -> None:
    assert route_mode("Create an HTML page", GenerationMode.ANSWER) == GenerationMode.ANSWER
