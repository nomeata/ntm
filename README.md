# ntm – Verwaltung von Therapiematerialien

Eine kleine Webanwendung für genau eine Nutzerin: Materialien erfassen (Titel,
Markdown-Text, Altersbereich, Schlagworte, Fundort) und später schnell
wiederfinden. Kein Datenbankserver – ein Verzeichnis mit einer
JSON-Datei pro Eintrag.

## Auf einen Blick

* **Backend**: FastAPI + uvicorn. Suche, Tag-Hierarchie und Altersfilter liegen
  vollständig im Python-Teil, damit es genau eine getestete Wahrheit gibt.
* **Frontend**: eine Single-Page-Anwendung aus Vanilla-JavaScript, kein
  Build-Schritt, keine npm-Abhängigkeiten. Das hält das Nix-Paket zu einem
  reinen Python-Paket und lässt der Tastatursteuerung freie Hand.
* **Speicher**: `<Datenverzeichnis>/<id>.json`, atomar geschrieben. Die Dateien
  sind von Hand editierbar; Änderungen von außen merkt der Server selbst.

## Datenmodell

```json
{
  "schema_version": 1,
  "id": "01m0twa5kk9mratj",
  "title": "Kasus-Memory",
  "text": "## Ablauf\n\nDie Karten werden gemischt …",
  "age_from": 7,
  "age_to": 12,
  "tags": ["Sprache/Grammatik/Kasus", "Format/Spiel"],
  "book": "Sprachförderung konkret",
  "location": "S. 45 ff.",
  "created": "2026-08-24T21:30:00Z",
  "updated": "2026-08-24T21:30:00Z"
}
```

### Altersachse

Die Skala ist `5, 6, … 20, 21, Eltern`; `21` ist als „21+“ zu lesen, `Eltern`
ist der oberste Punkt der Achse. Ein Eintrag belegt einen zusammenhängenden
Bereich darauf: `5–12`, `14–21+`, `12–Eltern` oder auch nur `Eltern`. Gesucht
wird immer mit *einem* Wert (dem Alter der Patientin bzw. „Eltern“); angezeigt
wird, was diesen Punkt enthält. In der JSON steht `"Eltern"`, sonst eine Zahl.

Material, das sich an Kinder *und* Eltern richtet, ohne die Altersstufen
dazwischen abzudecken, bekommt einfach ein Schlagwort wie `Mit Eltern` – Tags
sind dafür der flexiblere Weg und werden im Code nicht gesondert behandelt.

### Schlagworte

Die Hierarchie steckt allein im Namen: `Sprache/Grammatik/Kasus`. Gespeichert
wird immer der volle Pfad. Wer nach `Sprache` filtert, bekommt auch alles aus
`Sprache/Grammatik/Kasus`; `Sprach` dagegen trifft nichts – die Grenze ist der
Schrägstrich. Groß-/Kleinschreibung ist beim Vergleichen egal, angezeigt wird
die zuerst verwendete Schreibweise.

Es gibt bewusst keine Tag-Verwaltung: Schlagworte entstehen beim Tippen. Weil
in den Einträgen nur Strings stehen, ist ein späteres Umbenennen oder
Verschieben ein Präfix-Rewrite über alle Dateien – `schema_version` hält die
Tür für solche Migrationen offen.

## Lokal starten

Mit Nix (Flakes aktiviert):

```console
$ nix develop
$ python -m ntm --data-dir ./data --port 8123
```

Ohne Nix genügt eine virtuelle Umgebung mit `fastapi`, `uvicorn`,
`markdown-it-py` und `linkify-it-py`:

```console
$ python -m venv venv && ./venv/bin/pip install -e .
$ NTM_DATA_DIR=./data ./venv/bin/ntm
```

Ohne gesetztes Passwort läuft die App **ungeschützt** (praktisch zum
Entwickeln, sie warnt beim Start). Mit Passwort:

```console
$ NTM_PASSWORD=geheim NTM_DATA_DIR=./data python -m ntm
```

### Konfiguration

| Variable            | CLI                | Vorgabe     |
| ------------------- | ------------------ | ----------- |
| `NTM_DATA_DIR`      | `--data-dir`       | `./data`    |
| `NTM_HOST`          | `--host`           | `127.0.0.1` |
| `NTM_PORT`          | `--port`           | `8123`      |
| `NTM_PASSWORD`      | –                  | leer        |
| `NTM_PASSWORD_FILE` | `--password-file`  | leer        |

## Deployment auf NixOS

```nix
{
  inputs.ntm.url = "github:…/ntm";   # oder "path:/pfad/zum/checkout"

  outputs = { nixpkgs, ntm, ... }: {
    nixosConfigurations.server = nixpkgs.lib.nixosSystem {
      modules = [
        ntm.nixosModules.default
        {
          services.ntm = {
            enable = true;
            port = 8123;
            dataDir = "/var/lib/ntm";
            passwordFile = "/run/secrets/ntm-password";  # z. B. via sops-nix/agenix
          };

          # Empfohlen: TLS davor.
          services.nginx.virtualHosts."material.example.org" = {
            enableACME = true;
            forceSSL = true;
            locations."/".proxyPass = "http://127.0.0.1:8123";
          };
        }
      ];
    };
  };
}
```

Optionen: `enable`, `package`, `address`, `port`, `dataDir`, `passwordFile`,
`password`, `user`, `group`, `openFirewall`. Genau eine der beiden Optionen
`password` und `passwordFile` muss gesetzt sein; `passwordFile` wird über
systemd-Credentials eingelesen und landet nicht im Nix-Store.

Der Dienst läuft als eigener Systembenutzer mit den üblichen
systemd-Härtungen und darf nur in `dataDir` schreiben.

### Sicherheit

Die Anmeldung ist absichtlich minimal: ein Passwort, kein Benutzername, keine
Rollen. Aus dem Passwort wird ein Token abgeleitet, das im Local Storage des
Browsers liegt; der Server hält dafür keinen Zustand. Beim Login geht das
Passwort im Klartext über die Verbindung – **die App gehört deshalb hinter
TLS**. Die Voreinstellung `address = "127.0.0.1"` erwartet genau das: einen
Reverse-Proxy davor.

### Sicherung

Das Datenverzeichnis ist ein Verzeichnis mit Textdateien – ein `git init` darin
und ein regelmäßiges `git commit -am backup` (oder das übliche Backup) reicht
völlig.

## Bedienung

**Erfassen** – der Ablauf läuft ohne Maus durch: `n` öffnet das Formular, der
Fokus steht im Titel, `Enter` springt jeweils ins nächste Feld (im Fließtext
`Tab`), `Strg+S` speichert, `Strg+Enter` speichert und legt gleich den nächsten
Eintrag an – Buch und Altersbereich bleiben dabei stehen. `Esc` bricht ab.

Schlagworte und Buch haben Typeahead. Getippt wird ein Präfix oder ein Stück
aus der Mitte (`kasus` findet `Sprache/Grammatik/Kasus`); die Liste zeigt am
Ende immer auch das gerade Getippte als neues Schlagwort an, damit sichtbar
ist, was `Enter` tun wird. `Esc` schließt die Liste, danach übernimmt `Enter`
den Text wörtlich.

**Suchen** – zuerst die Schlagwortfilter (beliebig viele, kombinierbar) und der
Alterswert, darunter die Volltextsuche über Titel und Fließtext: mehrere Wörter
sind UND-verknüpft, `"in Anführungszeichen"` bleibt zusammen, Umlaute sind egal
(`marchen`, `maerchen` und `Märchen` finden dasselbe). Die Trefferliste lässt
sich zwischen „nur Titel“ und „mit Angaben“ (Buch, Ort, Schlagworte)
umschalten. Alle Filter stehen in der URL, der Zurück-Button funktioniert also
auch auf dem Handy wie erwartet.

**Tastenkürzel** – auf der Suchseite bekommt bewusst kein Feld automatisch den
Fokus, damit die Buchstabenkürzel sofort greifen: `n` neuer Eintrag, `t`
Schlagwortfilter, `/` Volltextsuche, `v` Ansicht, `?` Hilfe. Steht der Cursor
doch in einem Feld, tun es dieselben Befehle mit Alt (`Alt+N`, `Alt+T`,
`Alt+F`, `Alt+V`, `Alt+H`) – oder `Esc`, das den Fokus wieder freigibt.

## Tests

```console
$ nix develop
$ pytest                                    # Backend
$ node test/frontend/smoke.mjs              # Frontend
$ nix flake check                           # beides, plus NixOS-Modul
```

**Backend**: die Kernlogik – Tag-Hierarchie und Typeahead
(`tests/test_tags.py`), Altersachse inklusive „Eltern“ (`tests/test_ages.py`),
Suche und Filterkombinationen (`tests/test_query.py`) –, dazu die Ablage
(`tests/test_store.py`) und die HTTP-Schnittstelle samt Anmeldung
(`tests/test_api.py`). Dieselben Tests laufen beim `nix build` mit.

**Frontend**: `test/frontend/smoke.mjs` lädt `app.js` in eine jsdom-Seite,
hängt ein nachgebautes Backend davor und spielt die Bedienung durch – vor
allem die Tastaturwege vom leeren Formular bis zum gespeicherten Eintrag,
Typeahead, Filter, Bearbeiten und Löschen. Vor dem ersten Lauf von Hand
einmal `npm install` in `test/frontend` (`nix flake check` bringt jsdom über
das eingecheckte Lockfile selbst mit).

jsdom ist die einzige npm-Abhängigkeit im Repo und wird ausschließlich für
diesen Test gebraucht: die Anwendung selbst kommt ohne JavaScript-Ökosystem
aus, und `nix build` fasst npm nicht an.

**NixOS-Modul**: `nix flake check` baut die systemd-Unit einer
Minimalkonfiguration, damit Tippfehler im Modul nicht erst auf dem Server
auffallen.
