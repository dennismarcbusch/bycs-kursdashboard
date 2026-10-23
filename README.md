# BYCS-Kursdashboard

Web-App für Lehrkräfte, um den Kursfortschritt (Aktivitätsabschluss) ihrer Klassen in
ByCS-Lernplattform-Kursen (Moodle) übersichtlich und grafisch auszuwerten.

Details zum Funktionsumfang, Datenmodell und den offenen Punkten: [REQUIREMENTS.md](REQUIREMENTS.md).

## Aktueller Stand (V1-Prototyp)

- Lokale Benutzerverwaltung: Ein Admin legt Benutzerkonten und **Klassengruppen** an (Fach/
  Jahrgang und Klasse im Namen, z. B. "ITS10 ITG10A") und ordnet Benutzer einer oder mehreren
  Gruppen zu. Lehrkräfte sehen nur ihre Gruppen; Admins sehen alle. LDAP ist als Option für
  später vorgesehen (nicht angebunden).
- **Soll-Stand** pro Klassengruppe (manuell): Aktivität oder Ende eines Themenbereichs, bis zu
  der die Klasse sein soll. Damit werden Vorn / Im Feld / Hinterher und die "fälligen" offenen
  Aufgaben bestimmt; ohne Soll-Stand entscheiden die Quartile der Klasse.
- CSV-Export des Moodle-Berichts "Aktivitätsabschluss" (Bericht: Fortschritt) manuell
  hochladen.
- Die Aktivitätenliste wird bei jedem Import neu aus der CSV-Kopfzeile bestimmt - neue
  Aktivitäten im Kurs werden automatisch erkannt.
- **Themenbereiche per Hashtag im Aktivitätsnamen:** Ein Kürzel am Namensende, z. B.
  `Checkliste ARP #ipv4`, ordnet die Aktivität einem Themenbereich zu. Das Thema wandert so
  mit der Aktivität, auch wenn Aktivitäten hinzukommen, wegfallen oder umsortiert werden.
  Ohne eigenen Namen heißt der Bereich wie das Kürzel; auf der Verwaltungsseite lässt sich
  ein lesbarer Name vergeben. Eine manuelle Zuordnung pro Aktivität hat Vorrang, Aktivitäten
  ohne Hashtag landen unter "Sonstige". Die Bereiche stehen in Kursreihenfolge.
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
cp .env.example .env   # Werte anpassen (SECRET_KEY, ADMIN_PASSWORD)
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

## Erster Admin

Entweder `ADMIN_PASSWORD` (und optional `ADMIN_USERNAME`) beim ersten Start setzen oder per
Kommandozeile anlegen:

```bash
flask --app wsgi create-admin mein-name --name "Mein Name"
```

Weitere Benutzer und Klassengruppen legt der Admin unter "Administration" an.

## Konfiguration

Alle Einstellungen erfolgen über Umgebungsvariablen (siehe `.env.example`):

| Variable | Bedeutung |
|---|---|
| `SECRET_KEY` | Flask Session-Secret, unbedingt in Produktion setzen |
| `ADMIN_USERNAME` | Benutzername des Erst-Admins (Standard `admin`) |
| `ADMIN_PASSWORD` | Legt beim allerersten Start (solange es keinen Benutzer gibt) einen Admin mit diesem Passwort an. Danach aus der `.env` entfernen. |
| `DATABASE_URL` | optional, überschreibt den Standard-SQLite-Pfad (`instance/app.db`) |
| `DEV_LOGIN_ENABLED` | `true`/`false` - **nur lokale Entwicklung**: blendet einen Login-Bypass als Admin `dev-admin` ein (`/dev-login`). In Produktion niemals setzen. |

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
  ein manuelles Migrieren/Neuanlegen der SQLite-Datei (zuletzt geändert: Benutzerverwaltung,
  Klassengruppen und Soll-Stand; eine ältere `instance/app.db` muss gelöscht werden, die
  Datenbank wird beim Start neu angelegt).
- Der Login hat keine Sperre nach Fehlversuchen und keinen Passwort-Reset per Mail; ein
  vergessenes Passwort setzt der Admin zurück.
- Jeder Import ersetzt den Stand komplett (Schüler:innen, Aktivitäten in CSV-Reihenfolge,
  Abschlüsse); aufbewahrt werden nur die letzten zwei Importe. Dauerhaft bleiben Klassen,
  Themenbereiche und deren Zuordnung (über den Aktivitätsnamen). Wird eine Aktivität in
  Moodle umbenannt, gilt sie als neue Aktivität und muss neu zugeordnet werden.
- Themenbereiche kommen aus Hashtags im Aktivitätsnamen oder aus manueller Zuordnung; die
  Moodle-Kursabschnitte stehen nicht im CSV-Export und werden nicht ausgelesen. Die
  Namen der Themenbereiche (zu einem Kürzel) werden pro Klasse gepflegt.
