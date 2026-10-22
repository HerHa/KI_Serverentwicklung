# KI_Serverentwicklung

Minimaler Webshop-Server mit FastAPI, Pydantic, SQLAlchemy und PostgreSQL.
Die API bietet Produkt-GETs mit Query-Parametern und ETags, POST mit
Pydantic-Validierung sowie PUT mit `If-Match`-Schutz vor Lost Updates.
Ein Produkt kann optionale 1:1-Details und mehrere 1:N-Bewertungen besitzen.
Produktänderungen verwenden eine Versionsnummer für optimistische Sperrung.

## PostgreSQL verbinden und Beispieldaten laden

Voraussetzung: Docker Desktop und `uv` sind installiert. PostgreSQL wird nicht
in diesem Repository gestartet. Verwendet wird die bereits eingerichtete
PostgreSQL-Instanz aus `C:\Zimmermann\fastapi\extras\compose\postgres`.
Die Compose-Datei dort verwendet aktuell `postgres:19beta4-trixie` (PostgreSQL 19
Beta), nicht PostgreSQL 18 und nicht `dhi.io/postgres`. Diese Anleitung bindet
sich an die vorhandene Konfiguration an, ohne das Image zu ändern.

1. Sicherstellen, dass die Named Volumes und Initialisierungsdateien gemäß
   `extras/compose/postgres/ReadMe.md` im bestehenden Projekt eingerichtet sind.
   Anschließend dort PostgreSQL starten:

   ```powershell
   Push-Location C:\Zimmermann\fastapi\extras\compose\postgres
   docker compose up -d
   Pop-Location
   ```

2. In der laufenden PostgreSQL-Instanz eine eigene Login-Rolle und Datenbank
   für dieses Projekt anlegen:

   ```powershell
   Push-Location C:\Zimmermann\fastapi\extras\compose\postgres
   docker compose exec postgres psql --dbname=postgres --username=postgres
   Pop-Location
   ```

   In der `psql`-Eingabe:

   ```sql
   CREATE ROLE web_shop LOGIN;
   \password web_shop
   CREATE DATABASE web_shop OWNER web_shop;
   ```

   `\password` fragt das Passwort interaktiv ab. Verwende ein eigenes Passwort,
   nicht das Beispielpasswort aus `.env.example`.

3. `.env` anlegen und dort dasselbe Passwort in `DATABASE_URL` eintragen:

   ```powershell
   Copy-Item .env.example .env
   ```

   `.env` wird nicht in Git eingecheckt. Falls das Passwort URL-Sonderzeichen
   enthält, müssen diese in der URL prozentkodiert werden.

4. Abhängigkeiten installieren, Schema erstellen und die drei Beispieldatensätze
   laden:

   ```powershell
   uv sync --all-groups
   uv run --env-file .env python -m web_shop.seed
   ```

Das Seed-Kommando legt die Tabellen an und fügt die drei Beispieldatensätze nur
ein, wenn noch keine Produkte existieren. Die Beispieldaten sind in
`src/web_shop/seed.py` definiert.

### Bestehende Datenbank aktualisieren

`create_all()` erstellt fehlende Tabellen, ergänzt aber keine Spalten in
bestehenden Tabellen. Daher vor dem nächsten API-Start einmal die Migration
`migrations/001_add_product_version.sql` in der Datenbank `web_shop` ausführen.
Die Verbindung muss das Schema `public` verwenden. Im SQL-Editor zuerst prüfen:

```sql
SELECT current_database(), current_schema();
```

Das Ergebnis muss `web_shop` und `public` sein. Danach die Migration ausführen;
sie fügt für vorhandene Produkte die Spalte `version` mit Startwert `1` hinzu.
Anschließend lässt sich die Spalte so prüfen:

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'product'
ORDER BY ordinal_position;
```

Bei einer neuen Datenbank ist diese manuelle Migration nicht nötig.

## API starten und testen

Die API starten:

```powershell
uv run --env-file .env uvicorn web_shop.app:app --reload
```

Danach sind die interaktive API-Dokumentation und die OpenAPI-Spezifikation unter
`http://127.0.0.1:8000/docs` bzw. `/openapi.json` erreichbar.

Beispiele:

```powershell
# Produkte mit Query-Parametern filtern und paginieren
Invoke-RestMethod "http://127.0.0.1:8000/products?name=Kaffee&limit=10"

# Ein Produkt anlegen; Details sind optional
$body = @{
    name = "Thermobecher"
    description = "Isolierbecher aus Edelstahl"
    price = 19.90
    stock = 12
    detail = @{ material = "Edelstahl"; dimensions = "500 ml" }
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/products" `
    -ContentType "application/json" -Body $body
```

`GET /products/{id}` liefert einen `ETag`. Für einen bedingten GET diesen Wert
als `If-None-Match` senden; bei unverändertem Inhalt antwortet die API mit
`304 Not Modified`. Für `PUT /products/{id}` ist ein aktueller `If-Match`-ETag
Pflicht. Fehlt er, kommt `428 Precondition Required`; ist der Datensatz
zwischenzeitlich geändert worden, kommt `412 Precondition Failed`. Die
Produktantwort enthält außerdem `version`: Sie beginnt bei `1` und wird bei
jedem erfolgreichen PUT erhöht. SQLAlchemy schreibt die Änderung nur, wenn die
Version seit dem Laden der Session unverändert ist; die PUT-Antwort liefert den
neuen ETag für das nächste Update zurück.

Tests sowie Ruff- und Ty-Prüfung:

```powershell
uv run pytest
uv run ruff check .
uv run ty check
```

Bewertungen lassen sich über `POST /products/{id}/reviews` anlegen und über
`GET /products/{id}/reviews` abrufen. Details eines Produkts werden über
`POST /products` angelegt und in Produktantworten mitgeliefert.

Die Verbindung erfolgt über `localhost:5432` mit TLS. Zum Stoppen der gemeinsam
genutzten PostgreSQL-Instanz:

```powershell
Push-Location C:\Zimmermann\fastapi\extras\compose\postgres
docker compose down
Pop-Location
```
