from urllib.parse import urlsplit, urlunsplit

from models.evidence import Evidence, ResearchCategory


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


class EvidenceStore:
    """Per-analysis in-memory evidence store with stable sequential IDs."""

    def __init__(self) -> None:
        self._items: list[Evidence] = []
        self._urls: set[str] = set()

    def add(self, evidence: Evidence) -> Evidence | None:
        key = canonical_url(str(evidence.source_url))
        if key in self._urls:
            return None
        self._urls.add(key)
        self._items.append(evidence)
        return evidence

    def get(self, evidence_id: str) -> Evidence | None:
        return next((item for item in self._items if item.evidence_id == evidence_id), None)

    def list(self, category: ResearchCategory | None = None) -> list[Evidence]:
        return [item for item in self._items if category is None or item.category == category]

    def next_id(self) -> str:
        return f"E-{len(self._items) + 1:03d}"
