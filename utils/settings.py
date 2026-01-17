from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import sys

from utils.logging import get_logger

logger = get_logger(__name__)

CURRENT_CONFIG_VERSION = 1
DEFAULT_SETTINGS = {
    "config_version": CURRENT_CONFIG_VERSION,
    "locale": "en",
    "fallback_locale": "en",
    "enable_missing_key_logs": False,
}


def get_default_settings(locale: str | None = None) -> dict:
    payload = DEFAULT_SETTINGS.copy()
    if locale:
        payload["locale"] = locale
    return payload


@dataclass
class Settings:
    config_version: int
    locale: str
    fallback_locale: str
    enable_missing_key_logs: bool

    @classmethod
    def from_dict(cls, payload: dict) -> "Settings":
        return cls(
            config_version=int(payload.get("config_version", CURRENT_CONFIG_VERSION)),
            locale=str(payload.get("locale", DEFAULT_SETTINGS["locale"])),
            fallback_locale=str(payload.get("fallback_locale", DEFAULT_SETTINGS["fallback_locale"])),
            enable_missing_key_logs=bool(payload.get("enable_missing_key_logs", False)),
        )

    def to_dict(self) -> dict:
        return {
            "config_version": self.config_version,
            "locale": self.locale,
            "fallback_locale": self.fallback_locale,
            "enable_missing_key_logs": self.enable_missing_key_logs,
        }


def get_user_settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / ".il2_campaign_tracker" / "settings.json"


def get_portable_flag_path(base_dir: Path) -> Path:
    return base_dir / "portable.mode"


def get_portable_settings_path(base_dir: Path) -> Path:
    return base_dir / "settings.json"


def _resolve_base_dir(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        return base_dir
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resolve_settings_path(base_dir: Path | None = None) -> Path:
    base_dir = _resolve_base_dir(base_dir)

    if get_portable_flag_path(base_dir).exists():
        return get_portable_settings_path(base_dir)

    return get_user_settings_path()


def _read_settings(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid settings JSON at %s: %s", path, exc)
        return None
    except OSError as exc:
        logger.warning("Unable to read settings at %s: %s", path, exc)
        return None
    if isinstance(payload, dict):
        return payload
    logger.warning("Settings payload at %s is not an object", path)
    return None


def _migrate_settings(payload: dict) -> tuple[dict, bool]:
    updated = False
    config_version = payload.get("config_version")

    if not isinstance(config_version, int) or config_version <= 0:
        payload["config_version"] = CURRENT_CONFIG_VERSION
        updated = True
    elif config_version > CURRENT_CONFIG_VERSION:
        logger.warning(
            "Settings config_version %s is newer than supported %s",
            config_version,
            CURRENT_CONFIG_VERSION,
        )
        return payload, False
    elif config_version < CURRENT_CONFIG_VERSION:
        payload["config_version"] = CURRENT_CONFIG_VERSION
        updated = True

    for key, default_value in DEFAULT_SETTINGS.items():
        if key not in payload:
            payload[key] = default_value
            updated = True

    return payload, updated


def save_settings(settings: Settings, path: Path | None = None) -> None:
    settings_path = path or resolve_settings_path()
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as file:
            json.dump(settings.to_dict(), file, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.warning("Unable to save settings at %s: %s", settings_path, exc)


def load_settings(base_dir: Path | None = None) -> Settings:
    settings_path = resolve_settings_path(base_dir)
    payload = _read_settings(settings_path)

    if payload is None:
        return Settings.from_dict(get_default_settings())

    payload, updated = _migrate_settings(payload)
    settings = Settings.from_dict(payload)

    if updated:
        save_settings(settings, settings_path)

    return settings
