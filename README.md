# KI_Serverentwicklung

Kleine Python-Anwendung mit PostgreSQL und SQLAlchemy. Die Datenbankbasis wird
zunächst ohne REST-Schnittstelle aufgebaut.

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
   uv sync
   uv run --env-file .env python -m web_shop.seed
   ```

Das Seed-Kommando legt die Tabelle `product` in der Datenbank `web_shop` an.
Wenn sie bereits Datensätze enthält, fügt es keine weiteren Beispieldaten hinzu.
Die Beispieldaten sind in `src/web_shop/seed.py` definiert.

Die Verbindung erfolgt über `localhost:5432` mit TLS. Zum Stoppen der gemeinsam
genutzten PostgreSQL-Instanz:

```powershell
Push-Location C:\Zimmermann\fastapi\extras\compose\postgres
docker compose down
Pop-Location
```
