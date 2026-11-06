from dataclasses import dataclass, field
from pathlib import Path
import math
import os
import re
import tomllib
from zoneinfo import ZoneInfo


ROOT = Path(os.environ.get("VALREN_HOME", Path.cwd())).resolve()


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
    tutor_llm: dict = field(default_factory=dict)
    telegram: dict = field(default_factory=dict)
    agent_net: dict = field(default_factory=dict)

    def __post_init__(self):
        ZoneInfo(self.timezone)
        for name, ceiling in (("daily_limit", 20), ("candidate_limit", 1000), ("lookback_days", 90)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{name} must be an integer from 1 to {ceiling}")
        if type(self.monthly_budget_usd) not in (int, float) or not math.isfinite(self.monthly_budget_usd) or self.monthly_budget_usd < 0:
            raise ValueError("monthly_budget_usd must be finite and non-negative")
        if self.daily_limit > self.candidate_limit:
            raise ValueError("daily_limit exceeds candidate_limit")
        sections = {
            "interests": {"confirmed": bool, "topics": list, "excluded": list},
            "sources": {"arxiv_categories": list, "github_topics": list, "hf_tasks": list, "frontier_feeds": list},
            "llm": {"endpoint": str, "model": str, "input_per_million": float, "output_per_million": float,
                    "max_output_tokens": int, "reserve_input_tokens": int},
            "telegram": {"user_ids": list, "chat_ids": list},
            "agent_net": {"enabled": bool, "allowed_agents": list},
        }
        sections["tutor_llm"] = sections["llm"]
        for section, fields in sections.items():
            values = getattr(self, section)
            if not isinstance(values, dict) or set(values) - set(fields):
                raise ValueError(f"unknown fields in {section}")
            for key, value in values.items():
                kind = fields[key]
                if kind is float:
                    valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
                else:
                    valid = type(value) is kind
                if kind is list and valid:
                    member_type = int if section == "telegram" else str
                    valid = len(value) <= 20 and all(type(member) is member_type for member in value)
                if not valid:
                    raise ValueError(f"invalid {section}.{key}")
        for value in (self.notion_data_source_id, self.notion_profile_page_id):
            if not isinstance(value, str) or (value and not re.fullmatch(r"[a-fA-F0-9]{32}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}", value)):
                raise ValueError("invalid Notion ID")
        if not isinstance(self.notion_version, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.notion_version):
            raise ValueError("invalid Notion version")


def load(path: Path | None = None) -> Settings:
    with local_path(str(path or "config/settings.toml")).open("rb") as stream:
        return Settings(**tomllib.load(stream))


def local_path(value: str) -> Path:
    """Keep operational files under this checkout, including symlink resolution."""
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("operational path must stay inside valren")
    return path
