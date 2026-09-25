from __future__ import annotations

from pathlib import Path

from settings import load_settings


def test_local_config_overrides_nested_keys(tmp_path: Path):
    (tmp_path / "config.yaml").write_text(
        "project: p\nregion: r\nalert_email: ''\nbedrock:\n  llm_model_id: a\n  retrieval_results: 5\n"
    )
    (tmp_path / "config.local.yaml").write_text("alert_email: me@example.com\nbedrock:\n  llm_model_id: b\n")
    settings = load_settings(tmp_path / "config.yaml")
    assert settings.alert_email == "me@example.com"
    assert settings.bedrock == {"llm_model_id": "b", "retrieval_results": 5}


def test_committed_config_has_no_personal_email():
    import yaml

    root = Path(__file__).resolve().parents[1]
    assert not yaml.safe_load((root / "config.yaml").read_text())["alert_email"]
