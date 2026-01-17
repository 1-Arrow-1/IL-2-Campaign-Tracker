from __future__ import annotations

from pathlib import Path
import json

from utils.logging import get_logger
from utils.resources import resolve_locales_dir
from utils.settings import load_settings, Settings

logger = get_logger(__name__)

_LOCALE = "en"
_TRANSLATIONS: dict[str, object] = {}
_FALLBACK: dict[str, object] = {}
_SETTINGS: Settings | None = None


def _load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        logger.warning("Locale file not found: %s", path)
        return {}
    except json.JSONDecodeError as exc:
        logger.warning("Invalid locale JSON %s: %s", path, exc)
        return {}
    except OSError as exc:
        logger.warning("Unable to read locale file %s: %s", path, exc)
        return {}

    if isinstance(data, dict):
        return data
    logger.warning("Locale file %s does not contain a JSON object", path)
    return {}


def _merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _select_locale(settings: Settings) -> str:
    locale = settings.locale.strip() if settings.locale else ""
    fallback = settings.fallback_locale.strip() if settings.fallback_locale else ""
    return locale or fallback or "en"


def load_locale(base_dir: Path | None = None) -> None:
    global _LOCALE, _TRANSLATIONS, _FALLBACK, _SETTINGS

    _SETTINGS = load_settings(base_dir)
    locale = _select_locale(_SETTINGS)
    locales_dir = resolve_locales_dir()

    _FALLBACK = _load_json(locales_dir / "en.json")
    _LOCALE = locale

    if locale == "en":
        _TRANSLATIONS = _FALLBACK
        return

    selected = _load_json(locales_dir / f"{locale}.json")
    _TRANSLATIONS = _merge(_FALLBACK, selected)


def get_locale() -> str:
    return _LOCALE


def _get_setting_flag() -> bool:
    if _SETTINGS is None:
        return False
    return _SETTINGS.enable_missing_key_logs


def _resolve_key(key: str) -> object | None:
    value = _TRANSLATIONS.get(key)
    if value is not None:
        return value
    return _FALLBACK.get(key)


def t(key: str, **kwargs) -> str:
    value = _resolve_key(key)
    if value is None:
        if _get_setting_flag():
            logger.warning("Missing i18n key: %s", key)
        return key

    if isinstance(value, dict):
        if _get_setting_flag():
            logger.warning("Expected string for i18n key %s", key)
        return key

    text = str(value)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError) as exc:
            logger.warning("Format error for i18n key %s: %s", key, exc)
            return text
    return text


def _plural_category_en(count: int) -> str:
    return "one" if count == 1 else "other"


def _plural_category_ru(count: int) -> str:
    mod10 = count % 10
    mod100 = count % 100
    if mod10 == 1 and mod100 != 11:
        return "one"
    if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
        return "few"
    if mod10 == 0 or 5 <= mod10 <= 9 or 11 <= mod100 <= 14:
        return "many"
    return "other"


def _plural_category_pl(count: int) -> str:
    mod10 = count % 10
    mod100 = count % 100
    if count == 1:
        return "one"
    if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
        return "few"
    if mod10 == 0 or 5 <= mod10 <= 9 or 12 <= mod100 <= 14:
        return "many"
    return "other"


def _plural_category_fr(count: int) -> str:
    return "one" if count == 0 or count == 1 else "other"


def _plural_category_default(count: int) -> str:
    return "one" if count == 1 else "other"


def _get_plural_category(locale: str, count: int) -> str:
    normalized = locale.lower()
    if normalized.startswith("ru"):
        return _plural_category_ru(count)
    if normalized.startswith("pl"):
        return _plural_category_pl(count)
    if normalized.startswith("fr"):
        return _plural_category_fr(count)
    return _plural_category_default(count)


def tp(key: str, count: int, **kwargs) -> str:
    value = _resolve_key(key)
    if value is None:
        if _get_setting_flag():
            logger.warning("Missing i18n key: %s", key)
        return key

    if not isinstance(value, dict):
        if _get_setting_flag():
            logger.warning("Expected plural map for i18n key %s", key)
        return t(key, **kwargs)

    category = _get_plural_category(_LOCALE, int(count))
    text = value.get(category) or value.get("other")

    if text is None:
        if _get_setting_flag():
            logger.warning("Missing plural category %s for key %s", category, key)
        return key

    payload = dict(kwargs)
    payload.setdefault("count", count)
    try:
        return str(text).format(**payload)
    except (KeyError, ValueError) as exc:
        logger.warning("Format error for i18n key %s: %s", key, exc)
        return str(text)
