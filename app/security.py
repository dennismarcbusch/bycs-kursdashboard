"""Minimaler CSRF-Schutz: Jede POST-Anfrage muss das Token der Sitzung mitbringen.

Formulare binden es mit `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
ein; für fetch/XHR genügt der Header `X-CSRF-Token`.
"""

from __future__ import annotations

import hmac
import secrets

from flask import abort, current_app, request, session


def csrf_token() -> str:
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def _check_csrf():
    if not current_app.config.get("CSRF_ENABLED", True):
        return
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    expected = session.get("_csrf", "")
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    # Als Bytes vergleichen: compare_digest wirft bei Nicht-ASCII-Strings einen TypeError.
    if not expected or not hmac.compare_digest(expected.encode(), sent.encode()):
        abort(400, "Ungültiges oder fehlendes CSRF-Token. Seite neu laden und erneut versuchen.")


def init_csrf(app):
    app.before_request(_check_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token
