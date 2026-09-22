"""Sequenzielle Farbskala für Prozentwerte (Fortschritt), z. B. in der Heatmap.

Eine Hue (Blau, hell->dunkel) für Magnitude - siehe dataviz-Richtlinien: sequenzielle
Werte bekommen eine einzelne Farbfamilie statt einer Ampel/Regenbogen-Skala. Die
Endpunkte sind die dokumentierten Rampenstufen 100 und 700 der Referenzpalette;
dazwischen wird linear in sRGB interpoliert. Die Textfarbe wird je Zwischenwert
per WCAG-Kontrastformel berechnet statt geschätzt.
"""

from __future__ import annotations

_RAMP_LOW = (0xCD, 0xE2, 0xFB)  # Rampenstufe 100 (niedrig)
_RAMP_HIGH = (0x0D, 0x36, 0x6B)  # Rampenstufe 700 (hoch)

_TEXT_DARK = "#0b0b0b"
_TEXT_LIGHT = "#ffffff"


def _srgb_to_linear(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(l1: float, l2: float) -> float:
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def sequential_color(percent: float) -> tuple[str, str]:
    """(Hintergrundfarbe, Textfarbe) für einen Prozentwert 0-100 auf der Blau-Rampe."""
    t = max(0.0, min(1.0, percent / 100))
    rgb = tuple(round(low + (high - low) * t) for low, high in zip(_RAMP_LOW, _RAMP_HIGH))
    bg_hex = "#%02x%02x%02x" % rgb

    luminance = _relative_luminance(rgb)
    contrast_dark = _contrast(luminance, _relative_luminance((0x0B, 0x0B, 0x0B)))
    contrast_light = _contrast(luminance, 1.0)
    text_hex = _TEXT_DARK if contrast_dark >= contrast_light else _TEXT_LIGHT

    return bg_hex, text_hex
