"""LDAP-Authentifizierung gegen das UCS-AD.

Nur Mitglieder der konfigurierten Lehrkräfte-Gruppe (LDAP_TEACHER_GROUP_DN) dürfen sich
anmelden. Es werden keine Zugangsdaten persistiert - der Login-Vorgang bindet direkt gegen
das AD und wird danach verworfen.
"""

from ldap3 import Connection, Server
from ldap3.core.exceptions import LDAPBindError, LDAPException
from ldap3.utils.conv import escape_filter_chars
from flask import current_app


class LdapConfigError(RuntimeError):
    """Die LDAP-Konfiguration ist unvollständig oder fehlerhaft."""


def authenticate(username: str, password: str) -> str | None:
    """Prüft Login-Name/Passwort gegen das UCS-AD und die Gruppenmitgliedschaft.

    Gibt bei Erfolg den Anzeigenamen zurück (Fallback: username), sonst None.
    """
    username = (username or "").strip()
    if not username or not password:
        return None

    server = Server(current_app.config["LDAP_SERVER"], use_ssl=current_app.config["LDAP_USE_SSL"])
    user_dn = current_app.config["LDAP_USER_DN_TEMPLATE"].format(username=username)

    try:
        conn = Connection(server, user=user_dn, password=password, auto_bind=True)
    except LDAPBindError:
        return None
    except LDAPException:
        current_app.logger.exception("LDAP-Verbindung fehlgeschlagen")
        return None

    try:
        group_dn = current_app.config["LDAP_TEACHER_GROUP_DN"]
        safe_username = escape_filter_chars(username)
        conn.search(
            search_base=current_app.config["LDAP_BASE_DN"],
            search_filter=(
                f"(&(|(sAMAccountName={safe_username})(uid={safe_username}))"
                f"(memberOf={group_dn}))"
            ),
            attributes=["displayName"],
        )
        if not conn.entries:
            return None

        entry = conn.entries[0]
        if "displayName" in entry and str(entry.displayName):
            return str(entry.displayName)
        return username
    finally:
        conn.unbind()
