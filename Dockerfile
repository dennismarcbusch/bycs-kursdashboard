FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libldap2-dev libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Nicht als root laufen; das Datenverzeichnis gehört dem App-Benutzer.
RUN useradd --system --no-create-home app     && mkdir -p /app/instance     && chown app:app /app/instance
USER app
VOLUME ["/app/instance"]

EXPOSE 8000
# --preload: App (Tabellen, Erst-Admin, ggf. Zufalls-SECRET_KEY) einmal im Master anlegen,
# damit beide Worker denselben Stand und Schlüssel nutzen.
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "2", "--preload", "wsgi:app"]
