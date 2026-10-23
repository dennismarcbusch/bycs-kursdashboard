import os

# Platzhalter aus Doku/Beispielen. Sie gelten als "nicht gesetzt" (siehe app._ensure_secret_key).
INSECURE_SECRET_KEYS = {"dev-insecure-change-me", "change-me-to-a-random-value"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_BYTES", 5 * 1024 * 1024))
    # Zeitpunkte werden in UTC gespeichert und in dieser Zeitzone angezeigt.
    DISPLAY_TIMEZONE = os.environ.get("DISPLAY_TIMEZONE", "Europe/Berlin")

    LDAP_SERVER = os.environ.get("LDAP_SERVER", "ldap://localhost")
    LDAP_USE_SSL = os.environ.get("LDAP_USE_SSL", "false").lower() == "true"
    LDAP_BASE_DN = os.environ.get("LDAP_BASE_DN", "dc=schule,dc=local")
    LDAP_USER_DN_TEMPLATE = os.environ.get("LDAP_USER_DN_TEMPLATE", "{username}@schule.local")
    LDAP_TEACHER_GROUP_DN = os.environ.get(
        "LDAP_TEACHER_GROUP_DN", "cn=Lehrer,cn=groups,dc=schule,dc=local"
    )

    # Schutz vor Cross-Site-Request-Forgery für alle POST-Anfragen (siehe app/security.py).
    CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Hinter HTTPS auf true setzen, damit das Sitzungscookie nie unverschlüsselt übertragen wird.
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # Optionaler Erst-Admin: Gibt es noch keinen Benutzer und ist ADMIN_PASSWORD gesetzt,
    # wird beim Start ein Admin mit diesen Werten angelegt. Danach aus der Umgebung entfernen.
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

    # NUR für lokale Entwicklung ohne LDAP-Server: überspringt den LDAP-Login.
    # Muss in Produktion unbedingt false/unset bleiben.
    DEV_LOGIN_ENABLED = os.environ.get("DEV_LOGIN_ENABLED", "false").lower() == "true"
