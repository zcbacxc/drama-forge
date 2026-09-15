# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Configuration loading for Drama Forge (stdlib-only, movie-narrator style).

Layers (later does not overwrite earlier process env unless force=True):

1. Process environment (``DRAMA_FORGE_*``)
2. Project ``.env`` (cwd / package root)
3. User ``~/.drama-forge/.env`` (auto-created from ``.env.example`` once)

``.env.example`` in the project root is the committed source of truth for
available knobs. Secrets stay in ``.env`` / user config (both gitignored).
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_SRC_DIR = _PACKAGE_DIR.parent
_PROJECT_ROOT = _SRC_DIR.parent
_EXAMPLE_ENV = _PROJECT_ROOT / ".env.example"
_USER_DIR = Path.home() / ".drama-forge"
_USER_ENV = _USER_DIR / ".env"
_PROJECT_ENV = Path.cwd() / ".env"

_TRUTHY = {"1", "true", "yes", "on"}


def _read_example_env() -> str:
    """Return ``.env.example`` contents, or a short fallback template."""
    if _EXAMPLE_ENV.is_file():
        return _EXAMPLE_ENV.read_text(encoding="utf-8")
    return (
        "# Drama Forge — auto-generated minimal config\n"
        "DRAMA_FORGE_PROVIDER=mock\n"
        "DRAMA_FORGE_PROVIDER_DRY_RUN=1\n"
    )


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file (no export, # comments).

    Args:
            path: Path

    Returns:
            dict[str, str]
    """
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            result[key] = value
    return result


def ensure_user_config() -> Path:
    """Create ``~/.drama-forge/.env`` from ``.env.example`` if missing.

    Returns:
            Path
    """
    if _USER_ENV.exists():
        return _USER_ENV
    _USER_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=_USER_DIR, suffix=".env.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_read_example_env())
        os.replace(tmp_path, _USER_ENV)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    if not os.getenv("CI"):
        print(
            f"\n[drama-forge] 首次运行：已创建配置文件\n"
            f"  路径: {_USER_ENV}\n"
            f"  请编辑 DRAMA_FORGE_* 填入 Provider / API Key。\n"
            f"  项目目录 .env 优先于用户配置。\n",
            file=sys.stderr,
        )
    return _USER_ENV


def load_dotenv(
    *,
    project_env: Path | None = None,
    user_env: Path | None = None,
    environ: MutableMapping[str, str] | None = None,
    create_user_config: bool = True,
    force: bool = False,
) -> dict[str, str]:
    """Load .env layers into ``environ`` (default ``os.environ``).

    Args:
        project_env: Project-level .env path; default cwd/.env.
        user_env: User-level path; default ~/.drama-forge/.env.
        environ: Target mapping; defaults to ``os.environ``.
        create_user_config: Create user config from example if missing.
        force: When True, file values overwrite existing process env.

    Returns:
        The merged file values that were considered (not only those applied).
    """
    target: MutableMapping[str, str] = (
        environ if environ is not None else os.environ
    )
    if create_user_config:
        ensure_user_config()
    loaded: dict[str, str] = {}
    paths = (
        user_env if user_env is not None else _USER_ENV,
        project_env if project_env is not None else _PROJECT_ENV,
    )
    for path in paths:
        data = parse_env_file(path)
        for key, value in data.items():
            if force or key not in target:
                target[key] = value
            loaded[key] = value
    return loaded


@dataclass(slots=True)
class Settings:
    """Typed view of Drama Forge infrastructure configuration.

    Field names map to ``DRAMA_FORGE_*`` environment variables.
    Pipeline story content is not configured here (use story JSON / Manifest).
    """

    provider: str = "mock"
    provider_dry_run: bool = False
    artifact_root: str | None = None
    db_path: str | None = None

    # Generic OpenAI-compatible HTTP
    provider_base_url: str = "https://api.openai.com"
    provider_api_key: str = ""
    provider_api_key_env: str = "DRAMA_FORGE_PROVIDER_API_KEY"
    provider_model: str = "gpt-4o-mini"
    provider_timeout: float = 30.0
    provider_id: str = "openai-compatible"
    provider_chat_path: str = "v1/chat/completions"

    # DeepSeek (OpenAI-compatible preset)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_api_key: str = ""
    deepseek_api_key_env: str = "DRAMA_FORGE_DEEPSEEK_API_KEY"
    deepseek_model: str = "deepseek-flash"
    deepseek_timeout: float = 60.0
    deepseek_id: str = "deepseek"
    deepseek_chat_path: str = "chat/completions"

    # SiliconFlow image
    siliconflow_base_url: str = "https://api.siliconflow.cn"
    siliconflow_api_key: str = ""
    siliconflow_api_key_env: str = "DRAMA_FORGE_SILICONFLOW_API_KEY"
    siliconflow_image_model: str = "Kwai-Kolors/Kolors"
    siliconflow_image_size: str = "1024x1024"
    siliconflow_id: str = "siliconflow-image"

    # Agnes gateway (image + video)
    agnes_base_url: str = "https://api.example.com/v1"
    agnes_api_key: str = ""
    agnes_api_key_env: str = "DRAMA_FORGE_AGNES_API_KEY"
    agnes_image_model: str = "agnes-image-2.0-flash"
    agnes_image_id: str = "agnes-image"
    agnes_video_model: str = "agnes-video-2.5-flash"
    agnes_video_mode: str = "t2v"
    agnes_video_id: str = "agnes-video"
    agnes_timeout: float = 120.0

    live_smoke: bool = False

    @classmethod
    def from_environ(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build Settings from an environment mapping (default ``os.environ``).

        Args:
                    environ: default None

        Returns:
                    Settings
        """
        env = os.environ if environ is None else environ

        def get(key: str, default: str = "") -> str:
            value = env.get(key)
            if value is None:
                return default
            return str(value).strip()

        def get_opt(key: str) -> str | None:
            value = get(key)
            return value or None

        def get_bool(key: str) -> bool:
            return get(key).lower() in _TRUTHY

        def get_float(key: str, default: float) -> float:
            raw = get(key)
            if not raw:
                return default
            try:
                return float(raw)
            except ValueError:
                return default

        return cls(
            provider=get("DRAMA_FORGE_PROVIDER", "mock"),
            provider_dry_run=get_bool("DRAMA_FORGE_PROVIDER_DRY_RUN"),
            artifact_root=get_opt("DRAMA_FORGE_ARTIFACT_ROOT"),
            db_path=get_opt("DRAMA_FORGE_DB_PATH"),
            provider_base_url=get(
                "DRAMA_FORGE_PROVIDER_BASE_URL", "https://api.openai.com"
            ),
            provider_api_key=get("DRAMA_FORGE_PROVIDER_API_KEY"),
            provider_api_key_env=get(
                "DRAMA_FORGE_PROVIDER_API_KEY_ENV", "DRAMA_FORGE_PROVIDER_API_KEY"
            ),
            provider_model=get("DRAMA_FORGE_PROVIDER_MODEL", "gpt-4o-mini"),
            provider_timeout=get_float("DRAMA_FORGE_PROVIDER_TIMEOUT", 30.0),
            provider_id=get("DRAMA_FORGE_PROVIDER_ID", "openai-compatible"),
            provider_chat_path=get(
                "DRAMA_FORGE_PROVIDER_CHAT_PATH", "v1/chat/completions"
            ),
            deepseek_base_url=get(
                "DRAMA_FORGE_DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            ),
            deepseek_api_key=get("DRAMA_FORGE_DEEPSEEK_API_KEY"),
            deepseek_api_key_env=get(
                "DRAMA_FORGE_DEEPSEEK_API_KEY_ENV", "DRAMA_FORGE_DEEPSEEK_API_KEY"
            ),
            deepseek_model=get("DRAMA_FORGE_DEEPSEEK_MODEL", "deepseek-flash"),
            deepseek_timeout=get_float("DRAMA_FORGE_DEEPSEEK_TIMEOUT", 60.0),
            deepseek_id=get("DRAMA_FORGE_DEEPSEEK_ID", "deepseek"),
            deepseek_chat_path=get(
                "DRAMA_FORGE_DEEPSEEK_CHAT_PATH", "chat/completions"
            ),
            siliconflow_base_url=get(
                "DRAMA_FORGE_SILICONFLOW_BASE_URL", "https://api.siliconflow.cn"
            ),
            siliconflow_api_key=get("DRAMA_FORGE_SILICONFLOW_API_KEY"),
            siliconflow_api_key_env=get(
                "DRAMA_FORGE_SILICONFLOW_API_KEY_ENV",
                "DRAMA_FORGE_SILICONFLOW_API_KEY",
            ),
            siliconflow_image_model=get(
                "DRAMA_FORGE_SILICONFLOW_IMAGE_MODEL", "Kwai-Kolors/Kolors"
            ),
            siliconflow_image_size=get(
                "DRAMA_FORGE_SILICONFLOW_IMAGE_SIZE", "1024x1024"
            ),
            siliconflow_id=get("DRAMA_FORGE_SILICONFLOW_ID", "siliconflow-image"),
            agnes_base_url=get(
                "DRAMA_FORGE_AGNES_BASE_URL", "https://api.example.com/v1"
            ),
            agnes_api_key=get("DRAMA_FORGE_AGNES_API_KEY"),
            agnes_api_key_env=get(
                "DRAMA_FORGE_AGNES_API_KEY_ENV", "DRAMA_FORGE_AGNES_API_KEY"
            ),
            agnes_image_model=get(
                "DRAMA_FORGE_AGNES_IMAGE_MODEL", "agnes-image-2.0-flash"
            ),
            agnes_image_id=get("DRAMA_FORGE_AGNES_IMAGE_ID", "agnes-image"),
            agnes_video_model=get(
                "DRAMA_FORGE_AGNES_MODEL", "agnes-video-2.5-flash"
            ),
            agnes_video_mode=get("DRAMA_FORGE_AGNES_MODE", "t2v"),
            agnes_video_id=get("DRAMA_FORGE_AGNES_ID", "agnes-video"),
            agnes_timeout=get_float("DRAMA_FORGE_AGNES_TIMEOUT", 120.0),
            live_smoke=get_bool("DRAMA_FORGE_LIVE_SMOKE"),
        )

    def to_env_dict(self) -> dict[str, str]:
        """Export as ``DRAMA_FORGE_*`` env vars (used by factory bridges).

        Returns:
                    dict[str, str]
        """
        mapping = {
            "DRAMA_FORGE_PROVIDER": self.provider,
            "DRAMA_FORGE_PROVIDER_BASE_URL": self.provider_base_url,
            "DRAMA_FORGE_PROVIDER_API_KEY": self.provider_api_key,
            "DRAMA_FORGE_PROVIDER_API_KEY_ENV": self.provider_api_key_env,
            "DRAMA_FORGE_PROVIDER_MODEL": self.provider_model,
            "DRAMA_FORGE_PROVIDER_ID": self.provider_id,
            "DRAMA_FORGE_PROVIDER_CHAT_PATH": self.provider_chat_path,
            "DRAMA_FORGE_DEEPSEEK_BASE_URL": self.deepseek_base_url,
            "DRAMA_FORGE_DEEPSEEK_API_KEY": self.deepseek_api_key,
            "DRAMA_FORGE_DEEPSEEK_API_KEY_ENV": self.deepseek_api_key_env,
            "DRAMA_FORGE_DEEPSEEK_MODEL": self.deepseek_model,
            "DRAMA_FORGE_DEEPSEEK_ID": self.deepseek_id,
            "DRAMA_FORGE_DEEPSEEK_CHAT_PATH": self.deepseek_chat_path,
            "DRAMA_FORGE_SILICONFLOW_BASE_URL": self.siliconflow_base_url,
            "DRAMA_FORGE_SILICONFLOW_API_KEY": self.siliconflow_api_key,
            "DRAMA_FORGE_SILICONFLOW_API_KEY_ENV": self.siliconflow_api_key_env,
            "DRAMA_FORGE_SILICONFLOW_IMAGE_MODEL": self.siliconflow_image_model,
            "DRAMA_FORGE_SILICONFLOW_IMAGE_SIZE": self.siliconflow_image_size,
            "DRAMA_FORGE_SILICONFLOW_ID": self.siliconflow_id,
            "DRAMA_FORGE_AGNES_BASE_URL": self.agnes_base_url,
            "DRAMA_FORGE_AGNES_API_KEY": self.agnes_api_key,
            "DRAMA_FORGE_AGNES_API_KEY_ENV": self.agnes_api_key_env,
            "DRAMA_FORGE_AGNES_IMAGE_MODEL": self.agnes_image_model,
            "DRAMA_FORGE_AGNES_IMAGE_ID": self.agnes_image_id,
            "DRAMA_FORGE_AGNES_MODEL": self.agnes_video_model,
            "DRAMA_FORGE_AGNES_MODE": self.agnes_video_mode,
            "DRAMA_FORGE_AGNES_ID": self.agnes_video_id,
            "DRAMA_FORGE_AGNES_TIMEOUT": str(self.agnes_timeout),
            "DRAMA_FORGE_PROVIDER_TIMEOUT": str(self.provider_timeout),
            "DRAMA_FORGE_DEEPSEEK_TIMEOUT": str(self.deepseek_timeout),
        }
        if self.provider_dry_run:
            mapping["DRAMA_FORGE_PROVIDER_DRY_RUN"] = "1"
        if self.artifact_root:
            mapping["DRAMA_FORGE_ARTIFACT_ROOT"] = self.artifact_root
        if self.db_path:
            mapping["DRAMA_FORGE_DB_PATH"] = self.db_path
        if self.live_smoke:
            mapping["DRAMA_FORGE_LIVE_SMOKE"] = "1"
        # Drop empty optional secrets so factory env maps stay clean
        return {k: v for k, v in mapping.items() if v != ""}

    def provider_env(self) -> dict[str, str]:
        """Environment mapping suitable for ``build_default_registry(env=...)``.

        Returns:
                    dict[str, str]
        """
        return self.to_env_dict()


_settings_cache: Settings | None = None


def get_settings(*, reload: bool = False, load_files: bool = True) -> Settings:
    """Return cached Settings after optionally loading .env layers.

    Args:
            reload: bool (keyword-only)
            load_files: bool (keyword-only)

    Returns:
            Settings
    """
    global _settings_cache
    if _settings_cache is not None and not reload:
        return _settings_cache
    if load_files:
        load_dotenv(create_user_config=True)
    _settings_cache = Settings.from_environ()
    return _settings_cache


def reset_settings_cache() -> None:
    """Clear the cached Settings instance (tests).

    Returns:
            None
    """
    global _settings_cache
    _settings_cache = None


__all__ = [
    "Settings",
    "ensure_user_config",
    "get_settings",
    "load_dotenv",
    "parse_env_file",
    "reset_settings_cache",
]
