"""Load config.yaml into a typed, immutable settings object for the CDK app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]

# Account IDs that host the SageMaker built-in XGBoost image, per Region
# (published in the SageMaker "Docker registry paths" documentation).
XGBOOST_REGISTRY = {
    "us-east-1": "683313688378",
    "us-east-2": "257758044811",
    "us-west-2": "246618743249",
    "eu-west-1": "141502667606",
    "eu-west-2": "764974769150",
    "eu-central-1": "492215442770",
    "eu-north-1": "662702820516",
    "ap-south-1": "720646828776",
    "ap-southeast-1": "121021644041",
    "ap-southeast-2": "783357654285",
    "ap-northeast-1": "354813040037",
}


@dataclass(frozen=True)
class Settings:
    raw: dict[str, Any]

    @property
    def project(self) -> str:
        return self.raw["project"]

    @property
    def region(self) -> str:
        return self.raw["region"]

    @property
    def alert_email(self) -> str:
        return (self.raw.get("alert_email") or "").strip()

    @property
    def budget_usd(self) -> float:
        return float(self.raw["monthly_budget_usd"])

    @property
    def bedrock(self) -> dict[str, Any]:
        return self.raw["bedrock"]

    @property
    def sagemaker(self) -> dict[str, Any]:
        return self.raw["sagemaker"]

    @property
    def quality_gate(self) -> dict[str, float]:
        return self.raw["quality_gate"]

    @property
    def runtime(self) -> dict[str, Any]:
        return self.raw["runtime"]

    @property
    def hosting(self) -> str:
        hosting = self.raw.get("web", {}).get("hosting", "cloudfront")
        if hosting not in ("cloudfront", "api"):
            raise ValueError("web.hosting must be 'cloudfront' or 'api'")
        return hosting

    @property
    def endpoint_name(self) -> str:
        return f"{self.project}-xgb"

    @property
    def schedule_name(self) -> str:
        return f"{self.project}-simulator"

    def xgboost_image(self) -> str:
        account = XGBOOST_REGISTRY.get(self.region)
        if not account:
            raise ValueError(f"add the SageMaker XGBoost registry account for {self.region} to settings.py")
        version = self.sagemaker["xgboost_version"]
        return f"{account}.dkr.ecr.{self.region}.amazonaws.com/sagemaker-xgboost:{version}"


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        merged[key] = _merge(base[key], value) if isinstance(value, dict) and isinstance(base.get(key), dict) else value
    return merged


def load_settings(path: Path = ROOT / "config.yaml") -> Settings:
    """config.yaml, with config.local.yaml (gitignored, personal values like the alert email) merged on top."""
    raw = yaml.safe_load(path.read_text())
    local = path.with_name("config.local.yaml")
    if local.exists():
        raw = _merge(raw, yaml.safe_load(local.read_text()) or {})
    return Settings(raw)
