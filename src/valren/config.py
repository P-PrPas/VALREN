from dataclasses import dataclass, field
from pathlib import Path
import math
import tomllib
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    timezone: str = "Asia/Bangkok"
    daily_limit: int = 3
    candidate_limit: int = 100
    lookback_days: int = 7
    monthly_budget_usd: float = 0.0
    notion_data_source_id: str = ""
    notion_profile_page_id: str = ""
    notion_version: str = "2026-03-11"
    interests: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    llm: dict = field(default_factory=dict)
    telegram: dict = field(default_factory=dict)
    agent_net: dict = field(default_factory=dict)

    def __post_init__(self):
        ZoneInfo(self.timezone)
        for name, ceiling in (("daily_limit", 20), ("candidate_limit", 1000), ("lookback_days", 90)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{name} must be an integer from 1 to {ceiling}")
        if not math.isfinite(self.monthly_budget_usd) or self.monthly_budget_usd < 0:
            raise ValueError("monthly_budget_usd must be finite and non-negative")
        if self.daily_limit > self.candidate_limit:
            raise ValueError("daily_limit exceeds candidate_limit")


def load(path: Path | None = None) -> Settings:
    with (path or ROOT / "config/settings.toml").open("rb") as stream:
        return Settings(**tomllib.load(stream))


def local_path(value: str) -> Path:
    """Keep operational files under this checkout, including symlink resolution."""
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("operational path must stay inside valren")
    return path
