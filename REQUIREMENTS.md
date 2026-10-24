# BYCS-Kursdashboard – Anforderungen (Requirements)

Repo: https://github.com/dennismarcbusch/bycs-kursdashboard

## 1. Ziel / Vision

Lehrkräfte sollen den Kursfortschritt (Aktivitätsabschluss) ihrer Schüler:innen in
ByCS-Lernplattform-Kursen (Moodle-Fork) übersichtlich und grafisch aufbereitet sehen können –
als Alternative zum unübersichtlichen Moodle-Standardbericht. Datengrundlage ist der
CSV-Export des Aktivitätsabschluss-Berichts. In V1 lädt die Lehrkraft die CSV selbst hoch (diese
Funktion bleibt dauerhaft erhalten); später soll die App die CSV auf Knopfdruck (V2) und ggf.
vollautomatisch (V3) über einen Login abrufen.

Versionsplan: **V1** CSV-Upload (Fokus jetzt) · **V2** halbautomatischer Abruf auf manuellen
Klick · **V3** ggf. vollautomatischer Abruf per Scheduler · **V4** Gruppen-Auswahl.
Eine Moodle-Webservice-API steht nicht zur Verfügung; der JSON-Export wurde getestet und
verworfen (keine Namen, kein stabiler Schlüssel, keine Klassenangabe, keine Datumswerte).

Kernfrage auf einen Blick: **Wie viele der im Kurs vorhandenen Aktivitäten haben die
Schüler:innen einer Klasse bereits abgeschlossen?** Weitere Auswertungen/Ansichten kommen
schrittweise hinzu – die Architektur muss dafür erweiterbar sein.

## 2. Nutzergruppen & Rollen

- **Lehrkräfte**: Arbeiten mit den Klassengruppen, die ihnen zugeordnet sind: CSV hochladen,
  Soll-Stand setzen, Themenbereiche pflegen, Dashboard ansehen. Sie sehen ausschließlich ihre
  eigenen Klassengruppen.
- **Admin**: Legt Benutzerkonten und **Klassengruppen** an, ordnet Benutzer einer oder mehreren
  Klassengruppen zu, setzt Passwörter zurück und deaktiviert/löscht Konten. Ein Admin sieht
  alle Klassengruppen und darf sie löschen. Den ersten Admin legt `ADMIN_PASSWORD` beim
  ersten Start oder `flask create-admin` an.
- **Klassengruppe** = ein Dashboard mit eigenem Namen. Fach/Jahrgang und Klasse stecken im frei
  gewählten Namen (z. B. "ITS10 ITG10A"); es gibt dafür kein eigenes Datenmodell.
- **Authentifizierung**: rein lokal mit Benutzername und Passwort (gehasht gespeichert).
  LDAP/UCS-AD ist als optionale Erweiterung für später vorgesehen (`app/auth/ldap_auth.py`
  liegt bereit, ist aber nicht angebunden).

## 3. Funktionale Anforderungen

### 3.1 V1 – CSV-Upload → Dashboard

- Lokaler Login (siehe 4.2); Benutzer und Klassengruppen verwaltet der Admin.
- Klassengruppen legt der Admin an (Name frei wählbar, z. B. "ITS10 ITG10A"); Lehrkräfte arbeiten
  mit den ihnen zugeordneten.
- Lehrkraft lädt für eine Klasse eine CSV-Datei (Moodle-Export "Aktivitätsabschluss") hoch.
  **Der Upload ist die Grundfunktion von V1 und bleibt in allen späteren Versionen als
  gleichwertiger Weg erhalten** (kein bloßer Fallback).
- Die App parst die CSV und erzeugt ein Dashboard für diese Klasse mit mindestens:
  - Gesamtfortschritt der Klasse (z. B. % abgeschlossener Aktivitäten über alle Schüler:innen
    und Aktivitäten hinweg).
  - Fortschritt pro Schüler:in (wie viele von X Aktivitäten abgeschlossen).
  - Fortschritt pro Aktivität (wie viele Schüler:innen haben diese Aktivität abgeschlossen).
- **Klassenansicht**: Rangliste mit Klassenmedian und Einstufung Vorn / Im Feld / Hinterher
  (oberes/unteres Quartil, ab 4 Lernenden), Veränderung seit dem letzten Import, Gruppenfilter,
  Liste der offenen Aufgaben je Aktivität, Heatmap nach Fortschritt sortiert.
- **Schülerdetail**: Auswahl ohne Umweg, offene Aktivitäten oben (Lücken zuerst = offen,
  obwohl danach im selben Themenbereich etwas erledigt wurde), Vergleich zum Median, Filter
  "nur offene".
- **Themenbereiche per Hashtag** (Entscheidung 2026-10-24): Die Zuordnung erfolgt über ein
  Kürzel am Ende des Aktivitätsnamens (`Checkliste ARP #ipv4`), weil Moodle die Kursabschnitte
  nicht exportiert und Kapitelnummern bei Umsortierungen brechen. Aktivitäten mit gleichem
  Kürzel (Groß-/Kleinschreibung egal) bilden einen Bereich, dessen Anzeigename optional
  pro Klasse vergeben wird (sonst das Kürzel). Eine manuelle Zuordnung hat Vorrang;
  Aktivitäten ohne Hashtag stehen unter "Sonstige". Die Hashtags erscheinen nicht in den
  Anzeigenamen der App.
- **Soll-Stand** (Entscheidung 2026-10-24: nur manuell): Die Lehrkraft wählt pro Klassengruppe
  eine Aktivität oder das Ende eines Themenbereichs, bis zu der die Klasse sein soll. Alle
  Aktivitäten bis einschließlich dieser Marke sind "fällig". Mit Soll-Stand gilt: Vorn = Soll
  vollständig erledigt, Im Feld = mindestens 70 % des Solls, Hinterher = weniger; ohne
  Soll-Stand entscheiden die Quartile der Klasse. Fällige offene Aufgaben werden in
  Rangliste, Heatmap, Offen-Liste und Schülerseite hervorgehoben. Fehlt die Marken-Aktivität
  nach einem Import, wird sie ignoriert und die Lehrkraft darauf hingewiesen. Eine
  datumsgesteuerte Marke ist bewusst nicht vorgesehen.
- **Dynamische Aktivitätsliste**: Aktivitäten im Kurs können sich zwischen zwei Auswertungen
  ändern (neue kommen hinzu, alte fallen ggf. weg). Das Datenmodell und der Import dürfen die
  Aktivitätsliste **nicht fest verdrahten** – jeder Import muss die im CSV enthaltenen
  Aktivitäten neu erkennen/abgleichen (Matching z. B. über Aktivitätsnamen, da Moodle keine
  stabile ID im Export mitliefert – muss anhand eines echten Beispiel-Exports verifiziert
  werden).
- Mehrfacher Import derselben Klasse ist möglich. Jeder Import ersetzt den Stand komplett (siehe
  Datenmodell); es bleiben nur der aktuelle und der vorherige Import erhalten. Ein längerer
  Verlauf ist bewusst nicht vorgesehen (Datensparsamkeit).
- Exakte CSV-Spaltenstruktur (Spaltennamen, Kodierung, Trennzeichen, Werte für
  "abgeschlossen"/"nicht abgeschlossen") muss anhand eines echten Beispiel-Exports geklärt
  werden, bevor der Parser implementiert wird (**offener Punkt, siehe 7**).

### 3.2 V2 – Halbautomatischer CSV-Abruf (auf Klick)

- Für jede Klasse wird eine **konfigurierbare Export-URL** (der Aktivitätsabschluss-Bericht mit
  CSV-Download-Parametern) hinterlegt.
- Die Lehrkraft löst den Abruf per Knopfdruck aus; die App loggt sich über einen zentralen
  **Dienst-Account** (Service-User) in die ByCS-Lernplattform ein, lädt die CSV und importiert
  sie wie einen Upload (Quelle "auto"/"manuell abgerufen").
- Zugangsdaten des Dienst-Accounts werden **nicht im Klartext** in DB/Repo gespeichert, sondern
  z. B. als Umgebungsvariable/Secret bzw. verschlüsselt abgelegt.
- Fehlerfälle (Login schlägt fehl, URL nicht erreichbar, Session abgelaufen, CSV-Format
  unerwartet) müssen erkannt und der Lehrkraft sichtbar gemacht werden (z. B. "letzter
  erfolgreicher Abruf: ...", Fehlerstatus je Klasse).
- Der Upload (V1) bleibt dauerhaft gleichwertig nutzbar.

### 3.3 V3 – Vollautomatischer Abruf (ggf.)

- Aufbauend auf V2: Die App ruft die CSVs regelmäßig selbst ab (Scheduler, Intervall
  konfigurierbar, z. B. täglich nachts). Ob V3 umgesetzt wird, ist offen und hängt von den
  Erfahrungen mit V2 ab.

### 3.4 V4 – Gruppen-Auswahl statt freier Klassenanlage

- Innerhalb eines ByCS-Kurses werden einzelne Klassen als **Moodle-Gruppen** gepflegt.
- Statt Klassen "blind" per URL anzulegen, soll die App die im Kurs vorhandenen Gruppen
  auslesen (z. B. via Moodle-Webservice-API, falls verfügbar, oder aus dem Export) und der
  Lehrkraft zur Auswahl anbieten.
- Ein Dashboard bleibt weiterhin immer an **genau eine** Klasse/Gruppe gebunden.

### 3.5 Weitere Auswertungen (offen für Erweiterung)

Die Architektur (Datenmodell + Import) soll so ausgelegt sein, dass zusätzliche Auswertungen/
Ansichten ergänzt werden können, ohne den Import neu zu bauen, z. B. (Beispiele, nicht
abschließend, nicht zwingend Teil von V1):

- Zeitlicher Verlauf des Fortschritts (sofern historisierte Importe vorliegen; der Zuwachs seit
  dem letzten Import ist bereits umgesetzt).
- Export/Druckansicht für Elterngespräche.

## 4. Nicht-funktionale Anforderungen

### 4.1 Tech-Stack

- Backend: Python + Flask, Produktivbetrieb via Gunicorn.
- Datenbank: SQLite (Nutzer-/Klassen-/Import-Metadaten; die eigentlichen CSV-Rohdaten müssen
  nicht dauerhaft als Datei vorgehalten werden, sondern werden geparst in die DB übernommen).
- Frontend: Serverseitig gerendert (Flask/Jinja) mit einer JS-Chart-Bibliothek für die grafische
  Darstellung (z. B. Chart.js) – kein separates SPA-Framework nötig für den Funktionsumfang.
- Optional für später: LDAP-Anbindung über `ldap3` gegen das UCS-AD.

### 4.2 Authentifizierung & Autorisierung

- Lokale Benutzerverwaltung: Konten legt nur ein Admin an. Passwörter werden gehasht
  gespeichert (werkzeug), Mindestlänge 8 Zeichen; Benutzer können ihr Passwort selbst ändern.
- Deaktivierte oder gelöschte Konten verlieren sofort den Zugriff (der Benutzer wird bei jeder
  Anfrage aus der Datenbank geladen).
- Zugriff auf eine Klassengruppe nur für zugeordnete Lehrkräfte und Admins (403 sonst).
- Alle POST-Anfragen sind per CSRF-Token geschützt; Sitzungs-Cookie mit HttpOnly und
  SameSite=Lax; Weiterleitung nach dem Login nur auf interne Ziele.
- Sperre nach Fehlversuchen: je Benutzername (Standard 5) und je IP-Adresse (Standard 20)
  für 15 Minuten, gespeichert in der Datenbank; der Admin kann sie aufheben.
- Passwortänderung beendet alle anderen Sitzungen des Kontos.
- Nicht enthalten: Zwei-Faktor, Passwort-Zurücksetzen per Mail.
- Optional später: Anmeldung per LDAP gegen das UCS-AD (Gruppe "Lehrer"); die Konten würden
  dann beim ersten Login lokal angelegt und vom Admin Klassengruppen zugeordnet.

### 4.3 Datenschutz / Datenhaltung

- Sämtliche Schüler:innendaten (Namen, Fortschrittsdaten) verbleiben **ausschließlich lokal /
  on-prem** auf dem Server der Schule bzw. des Betreibers – keine Übertragung an externe
  Cloud-Dienste oder Drittanbieter-APIs (außer dem Zugriff auf die ByCS-Lernplattform selbst,
  die ohnehin die Datenquelle ist).
- Klarnamen der Schüler:innen dürfen verwendet werden (keine Pseudonymisierung gefordert).
- Keine externen Analytics-/Tracking-Skripte im Frontend.
- (Offen für später: Lösch-/Aufbewahrungsfristen für alte Importe – aktuell keine Vorgabe, siehe
  Punkt 7 offene Fragen.)

### 4.4 Deployment

- Zielbetrieb: **Docker-Container** auf einem Schul-/eigenen Server.
- Projekt liefert `Dockerfile` sowie `docker-compose.yml` (Flask/Gunicorn-Service + Volume für
  die SQLite-Datenbankdatei, damit Daten Container-Neustarts überleben).
- Konfiguration (Secret-Key, Erst-Admin, ggf. Dienst-Account-Credentials
  für V2/V3) über Umgebungsvariablen (`.env`, nicht eingecheckt).

### 4.5 Sonstiges

- Responsives, einfach bedienbares UI (Zielgruppe: Lehrkräfte, kein technisches Vorwissen
  vorausgesetzt).
- Fehlertoleranter CSV-Import: unerwartete/fehlende Spalten sollen zu einer verständlichen
  Fehlermeldung führen statt zu einem Absturz.

## 5. Grobes Datenmodell (Entwurf, wird in der Planungsphase verfeinert)

- **User**: Benutzername (eindeutig, klein geschrieben), Anzeigename, Passwort-Hash,
  Admin-Flag, aktiv-Flag.
- **ClassDashboard** (Klassengruppe): eindeutiger Name; Mitglieder (m:n zu User); Export-URL
  (für V2); Kurs-Referenz/Gruppe (für V4); **Soll-Stand** (Aktivitätsname). Dauerhaft gespeichert werden nur
  die Klasse, ihre **Themenbereiche** und die **Zuordnung Aktivitätsname → Themenbereich**.
- **Import**: gehört zu einer ClassDashboard; Zeitstempel; Quelle (Upload/Abruf). Ein Import
  ist ein in sich geschlossener **Schnappschuss**: Schüler:innen, Aktivitäten (in CSV-
  Reihenfolge) und Abschlüsse gehören zum Import und werden bei jedem Import komplett neu
  aufgebaut. Aufbewahrt werden nur die **letzten zwei Importe** (aktueller + vorheriger für
  „seit dem letzten Import"); ältere werden samt Schülerdaten gelöscht. Dadurch gibt es keine
  Altlasten entfallener Aktivitäten, und es liegen möglichst wenige Schülerdaten vor.
- **Activity**: Name und Position innerhalb eines Imports.
- **Student**: Name innerhalb eines Imports (gleiche Namen werden mit „(2)" unterschieden).
- **CompletionRecord**: Import × Student × Activity → abgeschlossen ja/nein, Abschlussdatum.

## 6. Nicht im Scope (V1)

- Schreibender Zugriff auf die ByCS-Lernplattform (die App liest nur Berichte, verändert nichts
  im Moodle-Kurs).
- Admin-Oberfläche / Verwaltung mehrerer Lehrkräfte durcheinander.
- Mobile App (nur responsives Web-Dashboard).
- Andere Berichte außer Aktivitätsabschluss (z. B. Noten) – potenzieller späterer Ausbau.

## 7. Offene Punkte (vor Umsetzung zu klären)

1. **Beispiel-CSV-Export** des Aktivitätsabschluss-Berichts wird benötigt, um den genauen
   Spaltenaufbau, das Trennzeichen, die Kodierung (UTF-8 vs. Windows-1252) und die exakten
   Statuswerte zu bestimmen, bevor der Import-Parser gebaut wird.
2. Genaue LDAP-Verbindungsdaten (Server, Port, TLS, Base-DN, Bind-Methode, Attributname für
   Gruppenmitgliedschaft) werden zur Implementierungszeit benötigt (kein Blocker für die
   Requirements, aber für V1-Umsetzung).
3. Für V2/V3 (Abruf): genaues Login-Verfahren der ByCS-Plattform (klassisches Formular-Login,
   evtl. Single-Sign-On/Shibboleth?) beeinflusst, ob ein einfacher HTTP-Session-Login reicht oder
   ein Headless-Browser (z. B. Playwright) nötig ist.
4. Lösch-/Aufbewahrungsfristen für Importe/Dashboards: aktuell keine Vorgabe – ggf. später
   nachziehen.
