# BYCS-Kursdashboard

Web-App für Lehrkräfte, um den Kursfortschritt (Aktivitätsabschluss) ihrer Klassen in
ByCS-Lernplattform-Kursen (Moodle) übersichtlich und grafisch auszuwerten.

Details zum Funktionsumfang, Datenmodell und den offenen Punkten: [REQUIREMENTS.md](REQUIREMENTS.md).

## Aktueller Stand (V1-Prototyp)

- Login via LDAP gegen das UCS-AD, beschränkt auf die Gruppe "Lehrer".
- Jede Lehrkraft verwaltet eigene Klassen-Dashboards.
- CSV-Export des Moodle-Berichts "Aktivitätsabschluss" (Bericht: Fortschritt) manuell
  hochladen.
- Die Aktivitätenliste wird bei jedem Import neu aus der CSV-Kopfzeile bestimmt - neue
  Aktivitäten im Kurs werden automatisch erkannt.
- Aktivitäten können manuell **Themenbereichen** zugeordnet werden (Verwaltungsseite pro
  Klasse; die Moodle-CSV enthält keine Information über Kursabschnitte). Die Zuordnung
  bleibt über künftige Importe erhalten, neue Aktivitäten landen zunächst unter "Sonstige".
- Dashboard zeigt: Gesamtfortschritt, Fortschritts-Kacheln pro Themenbereich, eine
  Heatmap (Schüler:innen × Aktivitäten, nach Themenbereich gruppiert) für den
  Klassenüberblick sowie eine Detailtabelle.
- Klick auf eine/n Schüler:in öffnet eine Detailseite mit einer nach Themenbereich
  gruppierten Checkliste (inkl. Abschlussdatum, falls im Export vorhanden).
- Klassenansicht mit Rangliste (Fortschritt, Klassenmedian, Einstufung Vorn / Im Feld /
  Hinterher nach Quartilen, Veränderung seit dem letzten Import), Gruppenfilter und einer
  Liste der offenen Aufgaben je Aktivität.
- Schülerdetail mit Schüler:innen-Auswahl, Liste der offenen Aktivitäten (Lücken zuerst,
  d. h. offen, obwohl danach im selben Themenbereich etwas erledigt wurde), Vergleich zum
  Median und Filter "nur offene".

Eine anonymisierte Test-CSV liegt in `tests/fixtures/demo_klasse.csv` (erfundene Namen).

Der CSV-Upload ist die Grundfunktion und bleibt dauerhaft erhalten. Geplant sind ein
halbautomatischer Abruf auf Klick per Service-User-Login (V2), ggf. ein vollautomatischer
Abruf (V3) und die Gruppen-Auswahl statt freier Klassenanlage (V4); siehe Requirements, noch
nicht implementiert.

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
| `DEV_LOGIN_ENABLED` | `true`/`false` - **nur lokale Entwicklung**: blendet einen Login-Bypass ohne LDAP ein (`/dev-login`). In Produktion niemals setzen. |

## Bekannte Einschränkungen (V1)

- Schüler:innen werden innerhalb eines Imports über den vollständigen Namen identifiziert
  (kein stabiler externer Schlüssel im CSV-Export vorhanden). Gleichnamige Schüler:innen
  werden mit „(2)" unterschieden; die Zuordnung zwischen zwei Importen für „seit dem letzten
  Import" läuft ebenfalls über den Namen.
- Der CSV-Parser erwartet das beobachtete Moodle-Exportformat (Name, E-Mail-Adresse,
  Institution, dann pro Aktivität eine Status- und optional eine Datumsspalte). Weicht ein
  Export davon ab (z. B. andere Spracheinstellung), muss `app/importer/csv_parser.py`
  angepasst werden.
- Kein Datenbank-Migrationswerkzeug (Flask-Migrate) - Schema-Änderungen erfordern aktuell
  ein manuelles Migrieren/Neuanlegen der SQLite-Datei (zuletzt geändert: Importe sind
  Schnappschüsse, siehe unten; eine ältere `instance/app.db` muss gelöscht werden).
- Jeder Import ersetzt den Stand komplett (Schüler:innen, Aktivitäten in CSV-Reihenfolge,
  Abschlüsse); aufbewahrt werden nur die letzten zwei Importe. Dauerhaft bleiben Klassen,
  Themenbereiche und deren Zuordnung (über den Aktivitätsnamen). Wird eine Aktivität in
  Moodle umbenannt, gilt sie als neue Aktivität und muss neu zugeordnet werden.
- Themenbereiche werden pro Klasse manuell gepflegt (kein Auto-Import aus Moodle-Kursabschnitten
  - das wäre erst mit der Moodle-API in V2/V3 möglich).
