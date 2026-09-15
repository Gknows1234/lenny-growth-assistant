from app.core.config import Settings
from app.repositories.knowledge import SearchHit, search_terms
from app.services.retrieval import Retriever


class FakeKnowledge:
    async def search(self, query: str, limit: int) -> list[SearchHit]:
        assert query == "activation"
        assert limit == 30
        return [
            SearchHit(f"c{i}", source, f"Title {source}", "Guest", "text", None, None, score)
            for i, (source, score) in enumerate(
                [("a", 1.0), ("a", 0.9), ("a", 0.8), ("b", 0.7), ("c", 0.6)]
            )
        ]


async def test_retrieval_diversifies_sources() -> None:
    settings = Settings(retrieval_limit=4)
    retriever = Retriever(FakeKnowledge(), settings)
    hits = await retriever.retrieve("activation")
    assert [item.source_id for item in hits] == ["a", "a", "b", "c"]


def test_citations_include_deep_link() -> None:
    hit = SearchHit("c1", "s1", "Episode", "Guest", "Excerpt", "https://youtu.be/id", 90, 1.0)
    citation = Retriever.citations([hit])[0]
    assert citation.id == "S1"
    assert citation.url == "https://youtu.be/id?t=90s"


def test_citations_reject_untrusted_source_url() -> None:
    hit = SearchHit("c1", "s1", "Episode", "Guest", "Excerpt", "javascript:alert(1)", 90, 1.0)
    assert Retriever.citations([hit])[0].url is None


def test_search_terms_remove_filler_and_preserve_product_language() -> None:
    assert search_terms(
        "How should an early-stage team find and validate product-market fit?"
    ) == ["early", "stage", "team", "find", "validate", "product", "market", "fit"]
