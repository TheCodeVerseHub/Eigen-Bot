"""Centralized programming language resource configuration and lookup helpers."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parents[1] / "cogs" / "data" / "language_resources.json"


@dataclass(frozen=True)
class ResourceLink:
    """A link shown in the resource embed."""

    label: str
    url: str


@dataclass(frozen=True)
class LanguageResource:
    """Configuration for a supported programming language."""

    key: str
    display_name: str
    aliases: tuple[str, ...]
    description: str
    documentation_url: str
    codeverse_hub_url: str
    related_channel_names: tuple[str, ...] = ()
    related_channel_ids: tuple[int, ...] = ()
    beginner_resources: tuple[ResourceLink, ...] = ()
    extra_resources: tuple[ResourceLink, ...] = ()

    @property
    def supported_terms(self) -> tuple[str, ...]:
        return (self.key, self.display_name, *self.aliases)


def _normalize(text: str) -> str:
    """Normalize text for case-insensitive and alias matching."""
    normalized = re.sub(r"[\s_\-./]+", " ", str(text).strip().lower())
    return " ".join(normalized.split())


def _read_json() -> Any:
    if not DATA_PATH.exists():
        logger.error("Language resource data file missing: %s", DATA_PATH)
        return []

    try:
        with DATA_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        logger.exception("Failed to read language resource data from %s: %s", DATA_PATH, exc)
        return []


def _parse_links(raw: Any, *, resource_key: str, field_name: str) -> tuple[ResourceLink, ...]:
    if not raw:
        return ()
    if not isinstance(raw, list):
        logger.warning(
            "Invalid %s for %s; expected a list, got %s",
            field_name,
            resource_key,
            type(raw).__name__,
        )
        return ()

    links: list[ResourceLink] = []
    for item in raw:
        if isinstance(item, str):
            label = item.strip()
            if not label:
                continue
            links.append(ResourceLink(label=label, url=item))
            continue

        if isinstance(item, dict):
            label = str(item.get("label", "")).strip()
            url = str(item.get("url", "")).strip()
            if not label or not url:
                logger.warning(
                    "Skipping malformed %s entry for %s: %s",
                    field_name,
                    resource_key,
                    item,
                )
                continue
            links.append(ResourceLink(label=label, url=url))
            continue

        logger.warning(
            "Skipping unsupported %s entry for %s: %r",
            field_name,
            resource_key,
            item,
        )

    return tuple(links)


def _parse_channel_names(raw: Any, *, resource_key: str) -> tuple[str, ...]:
    if not raw:
        return ()
    if not isinstance(raw, list):
        logger.warning(
            "Invalid related_channel_names for %s; expected a list, got %s",
            resource_key,
            type(raw).__name__,
        )
        return ()
    names = []
    for item in raw:
        value = str(item).strip()
        if value:
            names.append(value)
    return tuple(names)


def _parse_channel_ids(raw: Any, *, resource_key: str) -> tuple[int, ...]:
    if not raw:
        return ()
    if not isinstance(raw, list):
        logger.warning(
            "Invalid related_channel_ids for %s; expected a list, got %s",
            resource_key,
            type(raw).__name__,
        )
        return ()
    ids: list[int] = []
    for item in raw:
        try:
            ids.append(int(item))
        except Exception:
            logger.warning("Skipping invalid channel ID for %s: %r", resource_key, item)
    return tuple(ids)


def _parse_language_entry(raw: Any) -> LanguageResource | None:
    if not isinstance(raw, dict):
        logger.warning("Skipping malformed language resource entry: %r", raw)
        return None

    key = str(raw.get("key", "")).strip()
    display_name = str(raw.get("display_name", "")).strip()
    description = str(raw.get("description", "")).strip()
    documentation_url = str(raw.get("documentation_url", "")).strip()
    codeverse_hub_url = str(raw.get("codeverse_hub_url", "")).strip()

    if not key or not display_name or not description or not documentation_url or not codeverse_hub_url:
        logger.warning("Skipping incomplete language resource entry: %s", raw)
        return None

    aliases_raw = raw.get("aliases", [])
    aliases = tuple(
        alias
        for alias in (str(item).strip() for item in aliases_raw if item is not None)
        if alias
    ) if isinstance(aliases_raw, list) else ()
    if aliases_raw and not isinstance(aliases_raw, list):
        logger.warning("Invalid aliases list for %s; ignoring aliases", key)

    return LanguageResource(
        key=key,
        display_name=display_name,
        aliases=aliases,
        description=description,
        documentation_url=documentation_url,
        codeverse_hub_url=codeverse_hub_url,
        related_channel_names=_parse_channel_names(raw.get("related_channel_names", []), resource_key=key),
        related_channel_ids=_parse_channel_ids(raw.get("related_channel_ids", []), resource_key=key),
        beginner_resources=_parse_links(raw.get("beginner_resources", []), resource_key=key, field_name="beginner_resources"),
        extra_resources=_parse_links(raw.get("extra_resources", []), resource_key=key, field_name="extra_resources"),
    )


@lru_cache(maxsize=1)
def load_language_resources() -> tuple[LanguageResource, ...]:
    """Load and validate language resources from the centralized JSON file."""
    raw_data = _read_json()
    if isinstance(raw_data, dict):
        # Support either {"languages": [...]} or a bare list.
        raw_entries = raw_data.get("languages", [])
    else:
        raw_entries = raw_data

    if not isinstance(raw_entries, list):
        logger.error(
            "Language resource file must contain a list or a {\"languages\": [...]} object"
        )
        return ()

    resources: list[LanguageResource] = []
    seen_keys: set[str] = set()
    for raw_entry in raw_entries:
        resource = _parse_language_entry(raw_entry)
        if resource is None:
            continue

        normalized_key = _normalize(resource.key)
        if normalized_key in seen_keys:
            logger.warning("Duplicate language resource key ignored: %s", resource.key)
            continue

        seen_keys.add(normalized_key)
        resources.append(resource)

    return tuple(resources)


@lru_cache(maxsize=1)
def _resource_index() -> dict[str, LanguageResource]:
    """Build a normalized lookup index once."""
    index: dict[str, LanguageResource] = {}
    for resource in load_language_resources():
        for term in resource.supported_terms:
            normalized = _normalize(term)
            if not normalized:
                continue
            existing = index.get(normalized)
            if existing and existing.key != resource.key:
                logger.warning(
                    "Language lookup conflict for '%s' between %s and %s; keeping %s",
                    normalized,
                    existing.key,
                    resource.key,
                    existing.key,
                )
                continue
            index[normalized] = resource
    return index


def get_supported_language_names() -> list[str]:
    """Return supported language display names in configured order."""
    return [resource.display_name for resource in load_language_resources()]


def find_language_resource(query: str) -> LanguageResource | None:
    """Resolve a user query to a supported language resource."""
    normalized = _normalize(query)
    if not normalized:
        return None
    return _resource_index().get(normalized)


def suggest_language_names(query: str, *, limit: int = 5) -> list[str]:
    """Return display names closest to the user's input."""
    normalized = _normalize(query)
    if not normalized:
        return []

    resources = load_language_resources()
    if not resources:
        return []

    lookup: dict[str, str] = {}
    for resource in resources:
        for term in resource.supported_terms:
            lookup[_normalize(term)] = resource.display_name

    matches = get_close_matches(normalized, list(lookup.keys()), n=limit, cutoff=0.45)
    suggestions: list[str] = []
    for match in matches:
        display_name = lookup.get(match)
        if display_name and display_name not in suggestions:
            suggestions.append(display_name)
    return suggestions

