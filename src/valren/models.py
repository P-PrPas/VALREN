from dataclasses import asdict, dataclass, field
import re
from urllib.parse import urlsplit


KINDS = {"Repo", "Open model (LLM)", "Open model (CV)", "Frontier LLM", "Paper"}


def canonical(source: str, identifier: str) -> str:
    value = identifier.strip()
    if source == "arxiv":
        value = re.sub(r"^https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/", "", value)
        value = re.sub(r"v\d+$", "", value.removesuffix(".pdf"))
        if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})", value):
            raise ValueError("invalid arXiv ID")
    elif source == "github":
        if not re.fullmatch(r"[0-9]+", value) or int(value) < 1:
            raise ValueError("GitHub canonical ID requires numeric repository ID")
        value = str(int(value))
    elif source == "hf":
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value) or ".." in value:
            raise ValueError("invalid Hugging Face model ID")
    elif source == "frontier":
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
            raise ValueError("frontier release ID must be its primary HTTPS URL")
        value = parts._replace(netloc=parts.hostname.lower(), path=parts.path.rstrip("/"), fragment="").geturl()
    else:
        raise ValueError("unknown source")
    return f"{source}:{value}"


@dataclass
class Candidate:
    key: str
    title: str
    kind: str
    url: str
    published: str = ""
    text: str = ""
    aliases: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if any(not isinstance(getattr(self, field), str) for field in ("key", "title", "kind", "url", "published", "text")):
            raise ValueError("candidate text fields must be strings")
        if not isinstance(self.aliases, list) or any(not isinstance(a, str) or len(a) > 500 for a in self.aliases) or not isinstance(self.metadata, dict):
            raise ValueError("invalid aliases/metadata")
        if self.kind not in KINDS or not self.title.strip() or len(self.title) > 1000:
            raise ValueError("invalid candidate type/title")
        source, _, identifier = self.key.partition(":")
        if canonical(source, identifier) != self.key:
            raise ValueError("non-canonical candidate key")
        parts = urlsplit(self.url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
            raise ValueError("candidate requires HTTPS source URL")
        allowed = {"arxiv": ({"Paper"}, "arxiv.org"), "github": ({"Repo"}, "github.com"),
                   "hf": ({"Open model (LLM)", "Open model (CV)"}, "huggingface.co")}
        if source in allowed and (self.kind not in allowed[source][0] or parts.hostname != allowed[source][1]):
            raise ValueError("candidate source/type/host mismatch")
        if source == "frontier" and (self.kind != "Frontier LLM" or canonical(source, self.url) != self.key):
            raise ValueError("frontier key/type mismatch")
        self.text = self.text[:20000]

    def as_dict(self):
        return asdict(self)
