"""Load region definitions from config/regions.yml and settings from the environment."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
REGIONS_PATH = REPO_ROOT / "config" / "regions.yml"


class Settings(BaseSettings):
    """Environment-derived settings. Values come from .env on the VPS or process env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gfw_api_token: str = ""
    api_base_url: str = "http://localhost:8000"
    cors_origin: str = "http://localhost:8080"
    redis_url: str | None = None
    redis_password: str | None = None
    api_domain: str = "localhost"
    rate_limit: int = 60
    default_region: str = "default"
    grafana_admin_password: str | None = None


def load_regions(path: Path = REGIONS_PATH) -> dict:
    """Load region definitions from a YAML file. Returns a dict keyed by region name."""
    with open(path) as f:
        return yaml.safe_load(f)


def get_region(name: str, path: Path = REGIONS_PATH) -> dict:
    """Load a single region's config by name, raising KeyError if it is not defined."""
    regions = load_regions(path)
    return regions[name]
