# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for drama_forge.config (.env loading and Settings)."""

from __future__ import annotations

from pathlib import Path

from drama_forge.config import (
    Settings,
    ensure_user_config,
    get_settings,
    load_dotenv,
    parse_env_file,
    reset_settings_cache,
)


def test_parse_env_file_basic(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# comment\n"
        "FOO=bar\n"
        "export BAZ=qux\n"
        'QUOTED="hello world"\n'
        "EMPTY=\n"
        "NOEQ\n",
        encoding="utf-8",
    )
    data = parse_env_file(path)
    assert data["FOO"] == "bar"
    assert data["BAZ"] == "qux"
    assert data["QUOTED"] == "hello world"
    assert data["EMPTY"] == ""
    assert "NOEQ" not in data


def test_load_dotenv_does_not_overwrite_existing(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DRAMA_FORGE_PROVIDER=deepseek\n", encoding="utf-8")
    target = {"DRAMA_FORGE_PROVIDER": "mock"}
    load_dotenv(
        project_env=env_file,
        user_env=tmp_path / "missing.env",
        environ=target,
        create_user_config=False,
    )
    assert target["DRAMA_FORGE_PROVIDER"] == "mock"


def test_load_dotenv_force_overwrites(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DRAMA_FORGE_PROVIDER=deepseek\n", encoding="utf-8")
    target = {"DRAMA_FORGE_PROVIDER": "mock"}
    load_dotenv(
        project_env=env_file,
        user_env=tmp_path / "missing.env",
        environ=target,
        create_user_config=False,
        force=True,
    )
    assert target["DRAMA_FORGE_PROVIDER"] == "deepseek"


def test_settings_from_environ_defaults() -> None:
    settings = Settings.from_environ({})
    assert settings.provider == "mock"
    assert settings.deepseek_model == "deepseek-flash"
    assert settings.agnes_video_mode == "t2v"
    assert settings.provider_dry_run is False


def test_settings_from_environ_overrides() -> None:
    settings = Settings.from_environ(
        {
            "DRAMA_FORGE_PROVIDER": "production",
            "DRAMA_FORGE_PROVIDER_DRY_RUN": "yes",
            "DRAMA_FORGE_DEEPSEEK_MODEL": "deepseek-v4-pro",
            "DRAMA_FORGE_AGNES_BASE_URL": "http://gw/v1",
        }
    )
    assert settings.provider == "production"
    assert settings.provider_dry_run is True
    assert settings.deepseek_model == "deepseek-v4-pro"
    assert settings.agnes_base_url == "http://gw/v1"


def test_settings_to_env_dict_roundtrip() -> None:
    settings = Settings.from_environ(
        {
            "DRAMA_FORGE_PROVIDER": "deepseek+agnes-image",
            "DRAMA_FORGE_DEEPSEEK_API_KEY": "sk-test",
        }
    )
    exported = settings.provider_env()
    again = Settings.from_environ(exported)
    assert again.provider == "deepseek+agnes-image"
    assert again.deepseek_api_key == "sk-test"


def test_ensure_user_config_idempotent(tmp_path: Path, monkeypatch) -> None:
    user_dir = tmp_path / "home" / ".drama-forge"
    monkeypatch.setattr("drama_forge.config._USER_DIR", user_dir)
    monkeypatch.setattr("drama_forge.config._USER_ENV", user_dir / ".env")
    monkeypatch.setenv("CI", "1")
    path1 = ensure_user_config()
    assert path1.is_file()
    content = path1.read_text(encoding="utf-8")
    assert "DRAMA_FORGE" in content
    path2 = ensure_user_config()
    assert path2 == path1
    # does not overwrite
    path1.write_text("DRAMA_FORGE_PROVIDER=custom\n", encoding="utf-8")
    ensure_user_config()
    assert "custom" in path1.read_text(encoding="utf-8")


def test_get_settings_cache_and_reload(monkeypatch) -> None:
    reset_settings_cache()
    monkeypatch.setenv("DRAMA_FORGE_PROVIDER", "mock")
    monkeypatch.setattr("drama_forge.config.load_dotenv", lambda **kwargs: {})
    s1 = get_settings(reload=True, load_files=False)
    monkeypatch.setenv("DRAMA_FORGE_PROVIDER", "deepseek")
    s2 = get_settings(reload=False, load_files=False)
    assert s1 is s2
    assert s2.provider == "mock"
    s3 = get_settings(reload=True, load_files=False)
    assert s3.provider == "deepseek"
    reset_settings_cache()
