"""Configuration must load predictably, reject invalid values, and hide the key."""

import pytest
from pydantic import ValidationError

from documind.core.config import ENV_FILE, Settings


def test_root_dotenv_loads_independently_of_working_directory(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=reviewer-key\nCHUNK_SIZE=800\n", encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("CHUNK_SIZE", raising=False)
    monkeypatch.chdir(tmp_path)
    config = Settings(_env_file=env)
    assert config.gemini_api_key.get_secret_value() == "reviewer-key"
    assert config.chunk_size == 800
    assert ENV_FILE.is_absolute()


def test_environment_overrides_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=file-key\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "environment-key")
    config = Settings(_env_file=env)
    assert config.gemini_api_key.get_secret_value() == "environment-key"


@pytest.mark.parametrize(
    "values",
    [
        {"database_url": "not-a-database-url"},
        {"database_url": "sqlite:///file.db"},
        {"max_upload_bytes": 0},
        {"max_pdf_pages": -1},
        {"max_chunks": "invalid"},
        {"chunk_size": 450},
        {"chunk_overlap": 300},
        {"embedding_dimensions": 1536},
        {"embedding_model": "another-model"},
    ],
)
def test_invalid_settings_fail_validation(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_key_is_hidden_from_repr_and_json():
    config = Settings(_env_file=None, gemini_api_key="private-reviewer-key")
    assert "private-reviewer-key" not in repr(config)
    assert "private-reviewer-key" not in config.model_dump_json()


def test_validation_messages_hide_input():
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, database_url="private-invalid-input")
    assert "private-invalid-input" not in str(caught.value)


def test_empty_key_allows_offline_checks():
    config = Settings(_env_file=None, gemini_api_key="")
    assert config.gemini_api_key.get_secret_value() == ""


def test_env_example_contains_all_settings_with_valid_defaults():
    from dotenv import dotenv_values

    template = dotenv_values(ENV_FILE.with_name(".env.example"))
    assert set(template) == {name.upper() for name in Settings.model_fields}
    assert template["GEMINI_API_KEY"] == ""
    config = Settings(_env_file=None, **{key.lower(): value for key, value in template.items()})
    assert config.retrieval_mode == "hybrid_rerank"
