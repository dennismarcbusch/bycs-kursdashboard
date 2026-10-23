"""Themen-Hashtags im Aktivitätsnamen.

Der Moodle-Export enthält keine Kursabschnitte. Als einfachster, reihenfolge- und
änderungssicherer Weg gilt daher: Ein Hashtag am Ende des Aktivitätsnamens ordnet die
Aktivität einem Thema zu, z. B. "Checkliste ARP #ipv4". Das Thema wandert so mit der
Aktivität mit, auch wenn Aktivitäten hinzukommen, wegfallen oder umsortiert werden.
"""

from __future__ import annotations

import re

# Hashtag am Ende; dahinter darf noch die Nummerierung "(2)" stehen, die der Import bei
# mehrfach vorkommenden Namen anhängt.
_TAG_AT_END = re.compile(r"\s#([\w-]+)((?:\s\(\d+\))?)\s*$")
_VALID_TAG = re.compile(r"^[\w-]+$")


def split_tag(name: str) -> tuple[str, str | None]:
    """Zerlegt einen Aktivitätsnamen in (Anzeigename ohne Hashtag, Hashtag oder None)."""
    match = _TAG_AT_END.search(name)
    if not match:
        return name, None
    return name[: match.start()] + match.group(2), match.group(1)


def normalize_tag(raw: str) -> str | None:
    """Bereinigt eine Eingabe ("#IPv4 " -> "IPv4"); None, wenn sie kein gültiges Kürzel ist."""
    tag = raw.strip().lstrip("#").strip()
    return tag if _VALID_TAG.match(tag) else None
