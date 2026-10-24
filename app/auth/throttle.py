"""Sperre nach Login-Fehlversuchen (Schutz gegen Passwort-Raten).

Gezählt wird je Benutzername und je IP-Adresse, in der Datenbank (damit alle gunicorn-Worker
denselben Stand sehen und ein Neustart die Sperre nicht aufhebt):

- Nach LOGIN_MAX_FAILURES Fehlversuchen für einen Benutzernamen ist dieser für
  LOGIN_LOCK_MINUTES gesperrt - auch das richtige Passwort hilft dann nicht.
- Nach LOGIN_MAX_FAILURES_PER_IP Fehlversuchen von einer Adresse ist diese gesperrt
  (bremst das Durchprobieren vieler Benutzernamen).

Auch nicht existierende Benutzernamen werden gezählt und gesperrt, damit die Antwort nicht
verrät, ob es ein Konto gibt. Fehlversuche verfallen, wenn LOGIN_LOCK_MINUTES lang keiner
dazukommt. Ein erfolgreicher Login setzt den Zähler des Benutzernamens zurück; ein Admin
kann eine Sperre aufheben (siehe admin.unlock_user).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import current_app, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import LoginThrottle


def _now() -> datetime:
    # Naiv in UTC speichern und vergleichen: SQLite liefert Zeitpunkte ohne Zeitzone zurück.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _keys(username: str) -> list[tuple[str, int]]:
    cfg = current_app.config
    return [
        (f"user:{username[:100]}", cfg["LOGIN_MAX_FAILURES"]),
        (f"ip:{request.remote_addr or '-'}", cfg["LOGIN_MAX_FAILURES_PER_IP"]),
    ]


def _lock_duration() -> timedelta:
    return timedelta(minutes=current_app.config["LOGIN_LOCK_MINUTES"])


def locked_until(username: str) -> datetime | None:
    """Zeitpunkt (UTC, naiv), bis zu dem Logins für diesen Namen bzw. diese Adresse gesperrt
    sind, oder None."""
    now = _now()
    rows = LoginThrottle.query.filter(LoginThrottle.key.in_([k for k, _ in _keys(username)])).all()
    until = [r.locked_until for r in rows if r.locked_until and r.locked_until > now]
    return max(until) if until else None


def minutes_until(moment: datetime) -> int:
    """Verbleibende Minuten bis `moment` (aufgerundet, mindestens 1)."""
    return max(1, -int(-(moment - _now()).total_seconds() // 60))


def register_failure(username: str) -> None:
    now = _now()
    for key, limit in _keys(username):
        row = LoginThrottle.query.filter_by(key=key).first()
        if row is None:
            row = LoginThrottle(key=key, failures=0)
            db.session.add(row)
        elif row.last_failure_at and now - row.last_failure_at > _lock_duration():
            row.failures = 0  # alte Fehlversuche verfallen
        row.failures += 1
        row.last_failure_at = now
        if row.failures >= limit:
            row.locked_until = now + _lock_duration()
            row.failures = 0
    try:
        db.session.commit()
    except IntegrityError:
        # Paralleler Fehlversuch hat die Zeile gerade angelegt; dieser eine zählt dann nicht.
        db.session.rollback()


def reset(username: str) -> None:
    """Zähler und Sperre für einen Benutzernamen löschen (nach Login oder durch den Admin)."""
    LoginThrottle.query.filter_by(key=f"user:{username[:100]}").delete()
    db.session.commit()


def user_locked_until(username: str) -> datetime | None:
    """Nur die Sperre des Benutzernamens (für die Admin-Ansicht), unabhängig von der IP."""
    row = LoginThrottle.query.filter_by(key=f"user:{username[:100]}").first()
    if row and row.locked_until and row.locked_until > _now():
        return row.locked_until
    return None
