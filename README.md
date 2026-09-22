# BYCS-Kursdashboard

Web-App für Lehrkräfte, um den Kursfortschritt (Aktivitätsabschluss) ihrer Klassen in
ByCS-Lernplattform-Kursen (Moodle) übersichtlich und grafisch auszuwerten.

Details zum Funktionsumfang, Datenmodell und den offenen Punkten: [REQUIREMENTS.md](REQUIREMENTS.md).

## Aktueller Stand (V1-Prototyp)

- Login via LDAP gegen das UCS-AD, beschränkt auf die Gruppe "Lehrer".
- Jede Lehrkraft verwaltet eigene Klassen-Dashboards.
- CSV-Export des Moodle-Berichts "Aktivitätsabschluss" (Bericht: Fortschritt) manuell
  hochladen.
- Dashboard zeigt Gesamtfortschritt, Fortschritt pro Schüler:in und pro Aktivität
  (Chart.js-Balkendiagramme + Tabelle).
- Die Aktivitätenliste wird bei jedem Import neu aus der CSV-Kopfzeile bestimmt - neue
  Aktivitäten im Kurs werden automatisch erkannt.

Automatischer CSV-Abruf per Login (V2) und Gruppen-Auswahl statt freier Klassenanlage (V3)
sind in den Requirements skizziert, aber noch nicht implementiert.

## Lokale Entwicklung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # Werte anpassen (SECRET_KEY, LDAP_*)
python wsgi.py
```

App läuft dann auf http://localhost:5000.

### Tests

```bash
pytest
```

## Deployment (Docker)

```bash
cp .env.example .env   # Werte anpassen
docker compose up -d --build
```

Die App läuft dann auf Port 8000. Die SQLite-Datenbank liegt im Docker-Volume
`instance-data` und überlebt Container-Neustarts.

## Konfiguration

Alle Einstellungen erfolgen über Umgebungsvariablen (siehe `.env.example`):

| Variable | Bedeutung |
|---|---|
| `SECRET_KEY` | Flask Session-Secret, unbedingt in Produktion setzen |
| `LDAP_SERVER` | z. B. `ldap://ucs.schule.local` |
| `LDAP_USE_SSL` | `true`/`false` |
| `LDAP_BASE_DN` | Such-Basis für die Gruppenprüfung |
| `LDAP_USER_DN_TEMPLATE` | Bind-DN/UPN-Vorlage, `{username}` wird ersetzt |
| `LDAP_TEACHER_GROUP_DN` | DN der Gruppe, die sich anmelden darf |
| `DATABASE_URL` | optional, überschreibt den Standard-SQLite-Pfad (`instance/app.db`) |

## Bekannte Einschränkungen (V1)

- Schüler:innen werden innerhalb einer Klasse über den vollständigen Namen identifiziert
  (kein stabiler externer Schlüssel im CSV-Export vorhanden). Bei zwei gleichnamigen
  Schüler:innen in derselben Klasse würden deren Daten aktuell zusammengeführt.
- Der CSV-Parser erwartet das beobachtete Moodle-Exportformat (Name, E-Mail-Adresse,
  Institution, dann pro Aktivität eine Status- und optional eine Datumsspalte). Weicht ein
  Export davon ab (z. B. andere Spracheinstellung), muss `app/importer/csv_parser.py`
  angepasst werden.
- Kein Datenbank-Migrationswerkzeug (Flask-Migrate) - Schema-Änderungen erfordern aktuell
  ein manuelles Migrieren/Neuanlegen der SQLite-Datei.
