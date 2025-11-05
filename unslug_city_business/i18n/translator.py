"""Simple translation helper used across the backend and supporting scripts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Dict


class TranslationError(RuntimeError):
    """Raised when the translation resources cannot be accessed."""


@dataclass(frozen=True)
class Translator:
    """Load translation strings from the packaged locale resources."""

    locale: str = "en"
    fallback_locale: str = "en"

    def __post_init__(self) -> None:
        translations = self._load_locale(self.locale)
        object.__setattr__(self, "_translations", translations)

        if self.fallback_locale == self.locale:
            fallback = translations
        else:
            fallback = self._load_locale(self.fallback_locale)
        object.__setattr__(self, "_fallback", fallback)

    def translate(self, key: str) -> str:
        """Return the translation for *key* or raise :class:`TranslationError`."""

        if key in self._translations:
            return self._translations[key]
        if key in self._fallback:
            return self._fallback[key]
        raise TranslationError(f"Translation for '{key}' not found")

    @staticmethod
    def _load_locale(locale: str) -> Dict[str, str]:
        locales_dir = resources.files(__package__).joinpath("locales")
        if not locales_dir.is_dir():
            raise TranslationError("Locale resources are missing")

        resource = locales_dir.joinpath(f"{locale}.json")
        if not resource.is_file():
            raise TranslationError(f"Locale '{locale}' is not available")

        try:
            data = json.loads(resource.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - guardrail
            raise TranslationError(f"Invalid translation file for '{locale}'") from exc

        if not isinstance(data, dict):
            raise TranslationError("Translation file must contain an object")

        return {str(key): str(value) for key, value in data.items()}


def get_available_locales() -> Dict[str, str]:
    """Return the list of bundled locale identifiers."""

    locales_dir = resources.files(__package__).joinpath("locales")
    if not locales_dir.is_dir():
        return {}

    locales = {}
    for resource in locales_dir.iterdir():
        if resource.suffix == ".json" and resource.is_file():
            locales[resource.stem] = resource.stem
    return locales
