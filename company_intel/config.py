from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json

@dataclass
class Settings:
    request_timeout: int = 20
    user_agent: str = "Mozilla/5.0 CompanyIntelligence/1.0"
    news_language: str = "zh-TW"
    news_country: str = "TW"
    news_ceid: str = "TW:zh-Hant"

def load_settings(path: str | Path = "config.json") -> Settings:
    p = Path(path)
    if not p.exists():
        return Settings()
    raw = json.loads(p.read_text(encoding="utf-8"))
    gn = raw.get("google_news", {})
    return Settings(
        request_timeout=int(raw.get("request_timeout", 20)),
        user_agent=str(raw.get("user_agent", Settings.user_agent)),
        news_language=str(gn.get("language", "zh-TW")),
        news_country=str(gn.get("country", "TW")),
        news_ceid=str(gn.get("ceid", "TW:zh-Hant")),
    )
