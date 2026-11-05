from dataclasses import asdict, dataclass, field
import re
from urllib.parse import urlsplit


KINDS = {"Repo", "Open model (LLM)", "Open model (CV)", "Frontier LLM", "Paper"}


def canonical(source: str, identifier: str) -> str:
    value = identifier.strip()
    if source == "arxiv":
        value = re.sub(r"^https?://(?:www\.)?arxiv.org/(?:abs|pdf)/", "", value)
        value = re.sub(r"v\d+$", "", value.removesuffix(".pdf"))
        if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})", value):
            raise ValueError("invalid arXiv ID")
    elif source == "github":
        if not value.isdecimal():
            raise ValueError("GitHub canonical ID requires numeric repository ID")
        value = str(int(value))
    elif source == "hf":
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", value):
            raise ValueError("invalid Hugging Face model ID")
    elif source == "frontier":
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname:
            raise ValueError("frontier release ID must be its primary HTTPS URL")
        value = parts._replace(fragment="", query="").geturl()
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
        if self.kind not in KINDS or not self.title.strip() or len(self.title) > 1000:
            raise ValueError("invalid candidate type/title")
        source, _, identifier = self.key.partition(":")
        if canonical(source, identifier) != self.key:
            raise ValueError("non-canonical candidate key")
        if urlsplit(self.url).scheme != "https" or not urlsplit(self.url).hostname:
            raise ValueError("candidate requires HTTPS source URL")
        self.text = self.text[:20000]

    def as_dict(self):
        return asdict(self)
