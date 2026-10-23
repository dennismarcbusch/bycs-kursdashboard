"""Import des ByCS/Moodle-CSV-Exports "Aktivitätsabschluss" (Bericht: Fortschritt).

Beobachtetes Format (siehe REQUIREMENTS.md, Punkt 7.1 - anhand eines echten Exports
verifiziert):

    <Name>,E-Mail-Adresse,Institution,<Aktivität 1>,,<Aktivität 2>,,...

- Spalte 0: vollständiger Name der/des Schüler:in (die Kopfzeile dieser Spalte ist bei
  Moodle i. d. R. leer).
- Es folgen bekannte Metadaten-Spalten (E-Mail-Adresse, Institution, ...), die wir nicht
  auswerten.
- Danach folgt für jede Aktivität ein Spaltenpaar: Status ("Abgeschlossen" /
  "Nicht abgeschlossen") und - falls in Moodle aktiviert - das Abschlussdatum in der
  direkt folgenden Spalte (deren Kopfzeile leer ist). Ist kein Datum konfiguriert, steht
  die nächste Aktivität direkt in der Folgespalte.

Da sich die Aktivitätenliste zwischen zwei Exports ändern kann, wird bei jedem Import neu
anhand der Kopfzeile bestimmt, welche Aktivitäten enthalten sind (siehe REQUIREMENTS.md 3.1).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from app.extensions import db
from app.models import Activity, CompletionRecord, Import, Student

# Bekannte Metadaten-Spalten zwischen dem Namen (immer Spalte 0) und dem Beginn der
# Aktivitäts-Spalten. Weitere Locale-Varianten können hier ergänzt werden.
KNOWN_META_HEADERS = {
    "e-mail-adresse",
    "email address",
    "institution",
    "abteilung",
    "department",
}

# Aufbewahrte Importe je Klasse: der aktuelle plus der vorherige (für "seit letztem Import").
KEEP_IMPORTS = 2

COMPLETED_VALUES = {"abgeschlossen", "completed", "erledigt"}

# Mögliche Zeitstempel-Formate in der Datumsspalte je Aktivität.
TIMESTAMP_FORMATS = ("%m/%d/%y %H:%M", "%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M")


class CsvParseError(Exception):
    """Die CSV-Datei konnte nicht (sinnvoll) eingelesen werden."""


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CsvParseError("Unbekannte Zeichenkodierung der CSV-Datei.")


def _parse_timestamp(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _locate_activity_columns(header: list[str]) -> list[tuple[str, int, int | None]]:
    """Bestimmt anhand der Kopfzeile, welche Spalten Aktivitäten sind.

    Gibt eine Liste von (Aktivitätsname, Status-Spaltenindex, Datum-Spaltenindex|None)
    zurück. Aktivitätsnamen, die mehrfach vorkommen, werden durchnummeriert, damit sie
    innerhalb der Klasse eindeutig bleiben.
    """
    if not header:
        raise CsvParseError("Die CSV-Datei enthält keine Kopfzeile.")

    i = 1  # Spalte 0 ist immer der Name.
    while i < len(header) and header[i].strip().lower() in KNOWN_META_HEADERS:
        i += 1

    activities: list[tuple[str, int, int | None]] = []
    seen_names: set[str] = set()

    while i < len(header):
        label = header[i].strip()
        if not label:
            i += 1
            continue

        name = _unique(label, seen_names)

        status_idx = i
        timestamp_idx = None
        if i + 1 < len(header) and header[i + 1].strip() == "":
            timestamp_idx = i + 1
            i += 2
        else:
            i += 1

        activities.append((name, status_idx, timestamp_idx))

    if not activities:
        raise CsvParseError(
            "Es konnten keine Aktivitäts-Spalten in der CSV-Datei gefunden werden."
        )
    return activities


def _is_completed(value: str) -> bool:
    return value.strip().lower() in COMPLETED_VALUES


def _unique(name: str, seen: set[str]) -> str:
    """Macht mehrfach vorkommende Namen eindeutig ("Name", "Name (2)", ...).

    Prüft gegen alle bereits vergebenen Namen, damit auch ein echter Name wie "Name (2)"
    nicht mit einer Nummerierung kollidiert (sonst Verletzung des Unique-Constraints)."""
    candidate, n = name, 1
    while candidate in seen:
        n += 1
        candidate = f"{name} ({n})"
    seen.add(candidate)
    return candidate


def import_csv(class_dashboard, file_stream, original_filename=None, source="upload") -> Import:
    """Importiert eine CSV-Datei als neuen, in sich geschlossenen Stand einer Klasse.

    Schüler:innen, Aktivitäten (in CSV-Reihenfolge) und Abschlüsse werden komplett neu
    aufgebaut. Aufbewahrt werden nur die letzten KEEP_IMPORTS Importe, ältere werden
    gelöscht. Dauerhaft bleiben Klasse, Themenbereiche und deren Zuordnung (über den
    Aktivitätsnamen).

    Ruft KEIN db.session.commit() auf - das obliegt dem Aufrufer (Route), damit Fehler vor
    dem Commit sauber behandelt werden können.
    """
    raw = file_stream.read()
    text = _decode(raw) if isinstance(raw, bytes) else raw

    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=","))
    except csv.Error as exc:  # z. B. NUL-Bytes oder übergroße Felder
        raise CsvParseError(f"Die Datei ist keine gültige CSV-Datei ({exc}).") from exc
    if not rows:
        raise CsvParseError("Die CSV-Datei ist leer.")

    header = rows[0]
    activity_columns = _locate_activity_columns(header)

    imp = Import(class_dashboard=class_dashboard, source=source, original_filename=original_filename)
    db.session.add(imp)

    activities = []
    for position, (name, status_idx, timestamp_idx) in enumerate(activity_columns):
        activity = Activity(import_=imp, position=position, name=name)
        db.session.add(activity)
        activities.append((activity, status_idx, timestamp_idx))

    seen_names: set[str] = set()
    imported_rows = 0
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        imported_rows += 1

        student = Student(import_=imp, full_name=_unique(row[0].strip(), seen_names))
        db.session.add(student)

        for activity, status_idx, timestamp_idx in activities:
            status_value = row[status_idx] if status_idx < len(row) else ""
            completed_at = None
            if timestamp_idx is not None and timestamp_idx < len(row):
                completed_at = _parse_timestamp(row[timestamp_idx])

            db.session.add(
                CompletionRecord(
                    import_=imp,
                    student=student,
                    activity=activity,
                    completed=_is_completed(status_value),
                    completed_at=completed_at,
                )
            )

    if imported_rows == 0:
        raise CsvParseError("Die CSV-Datei enthält keine auswertbaren Zeilen.")

    _prune_old_imports(class_dashboard, newest=imp)
    return imp


def _prune_old_imports(class_dashboard, newest: Import) -> None:
    """Löscht alte Importe, sodass der neue plus die jüngsten Vorgänger übrig bleiben."""
    db.session.flush()
    older = (
        Import.query.filter(
            Import.class_dashboard_id == class_dashboard.id, Import.id != newest.id
        )
        .order_by(Import.imported_at.desc(), Import.id.desc())
        .all()
    )
    for old in older[KEEP_IMPORTS - 1 :]:
        db.session.delete(old)
