"""Anmeldung, Rollen und Zugriff auf Klassengruppen (lokale Benutzerverwaltung)."""

from __future__ import annotations

import hashlib
import hmac
from functools import wraps

from flask import abort, current_app, redirect, request, session, url_for

from app.extensions import db
from app.models import ClassDashboard, User


_UNSET = object()


def _session_fingerprint(user: User) -> str:
    """Kennung des aktuellen Passworts für die Sitzung. Ändert sich das Passwort, passen alte
    Sitzungen (auch auf anderen Geräten) nicht mehr und gelten als abgemeldet. Das Cookie ist
    nur signiert, nicht verschlüsselt - daher ein HMAC statt eines Teils des Hashes."""
    key = current_app.secret_key
    key = key.encode() if isinstance(key, str) else key
    return hmac.new(key, f"{user.id}:{user.password_hash}".encode(), hashlib.sha256).hexdigest()[:32]


def log_in(user: User) -> None:
    """Beginnt eine frische Sitzung für den Benutzer (verhindert Session Fixation)."""
    session.clear()
    session["user_id"] = user.id
    session["pw"] = _session_fingerprint(user)


def current_user() -> User | None:
    """Der angemeldete Benutzer (aus der Datenbank, pro Anfrage gecacht) oder None.

    Deaktivierte oder gelöschte Konten und Sitzungen von vor einer Passwortänderung gelten
    sofort als abgemeldet. Der Cache hängt am
    Request-Objekt (nicht an `g`), damit er garantiert nur für diese eine Anfrage gilt."""
    cached = getattr(request, "_current_user", _UNSET)
    if cached is not _UNSET:
        return cached
    user = None
    user_id = session.get("user_id")
    if user_id is not None:
        user = db.session.get(User, user_id)
        if (
            user is None
            or not user.is_active
            or not hmac.compare_digest(session.get("pw", ""), _session_fingerprint(user))
        ):
            session.clear()
            user = None
    request._current_user = user
    return user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("auth.login", next=request.path))
        if not user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def accessible_dashboards(user: User) -> list[ClassDashboard]:
    """Klassengruppen, die der Benutzer sehen darf (Admins: alle)."""
    if user.is_admin:
        return ClassDashboard.query.order_by(ClassDashboard.name).all()
    return list(user.classes)


def get_accessible_dashboard(dashboard_id: int) -> ClassDashboard:
    """Lädt eine Klassengruppe oder bricht mit 404/403 ab, wenn kein Zugriff besteht."""
    user = current_user()
    cd = db.session.get(ClassDashboard, dashboard_id)
    if cd is None:
        abort(404)
    if not user.is_admin and cd not in user.classes:
        abort(403)
    return cd
