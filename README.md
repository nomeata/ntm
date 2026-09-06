# ntm – Verwaltung von Therapiematerialien

Eine kleine Webanwendung für eine Handvoll Nutzerinnen: Materialien erfassen
(Titel, Beschreibung in Markdown, Altersbereich, Schlagworte, Fundort) und
später schnell wiederfinden. Kein Datenbankserver – pro Nutzerin ein
Verzeichnis mit einer JSON-Datei pro Eintrag. Angemeldet wird ohne Passwort,
per Link in einer E-Mail.

## Auf einen Blick

* **Backend**: FastAPI + uvicorn. Suche, Tag-Hierarchie und Altersfilter liegen
  vollständig im Python-Teil, damit es genau eine getestete Wahrheit gibt.
* **Frontend**: eine Single-Page-Anwendung aus Vanilla-JavaScript, kein
  Build-Schritt, keine npm-Abhängigkeiten. Das hält das Nix-Paket zu einem
  reinen Python-Paket und lässt der Tastatursteuerung freie Hand.
* **Speicher**: `<Datenverzeichnis>/<adresse>/<id>.json`, atomar geschrieben.
  Die Dateien sind von Hand editierbar; Änderungen von außen merkt der Server
  selbst. Jede Nutzerin hat ihren eigenen Bestand – auch Schlagworte und
  Bücherlisten sind getrennt.

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

Ohne gesetzte Nutzerliste läuft die App **ungeschützt** und mit einem
einzigen Bestand direkt im Datenverzeichnis (praktisch zum Entwickeln, sie
warnt beim Start). Mit Nutzerliste verlangt sie die Anmeldung per Mail-Link;
zum lokalen Ausprobieren kann `NTM_SENDMAIL` auf ein Skript zeigen, das die
Mail einfach in eine Datei schreibt:

```console
$ NTM_USERS=anna@example.org NTM_MAIL_FROM=ntm@example.org python -m ntm
```

### Konfiguration

| Variable        | CLI          | Vorgabe                          |
| --------------- | ------------ | -------------------------------- |
| `NTM_DATA_DIR`  | `--data-dir` | `./data`                         |
| `NTM_HOST`      | `--host`     | `127.0.0.1`                      |
| `NTM_PORT`      | `--port`     | `8123`                           |
| `NTM_USERS`     | –            | leer (Adressen, Komma-getrennt)  |
| `NTM_MAIL_FROM` | –            | leer                             |
| `NTM_SENDMAIL`  | –            | `sendmail`                       |
| `NTM_BASE_URL`  | –            | leer (dann aus dem Request)      |

## Deployment auf NixOS

```nix
{
  inputs.ntm.url = "github:nomeata/ntm";   # oder "path:/pfad/zum/checkout"
  inputs.ntm.inputs.nixpkgs.follows = "nixpkgs";

  outputs = { nixpkgs, ntm, ... }: {
    nixosConfigurations.server = nixpkgs.lib.nixosSystem {
      modules = [
        ntm.nixosModules.default
        {
          services.ntm = {
            enable = true;
            port = 8123;
            users = [ "anna@example.org" ];
            mailFrom = "ntm@example.org";
          };

          # Für die Login-Mails: irgendein lokaler MTA mit sendmail-Wrapper.
          services.nullmailer = {
            enable = true;
            config.me = "example.org";
            # … plus Zugangsdaten zum Smarthost, siehe nullmailer-Doku.
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

Das `follows` ist Absicht: damit baut der Dienst gegen dasselbe nixpkgs wie der
Rest des Systems, teilt sich Python und die Bibliotheken mit ihm und zieht
keinen zweiten nixpkgs-Baum in den Store. Nachgeprüft ist das Bauen gegen
`nixos-25.05`, `nixos-25.11` und das gepinnte nixpkgs; `nixos-24.11` scheitert
an setuptools < 77, das die Lizenzangabe nach PEP 639 noch nicht kennt. Wenn
es auf einem älteren System daran hakt: die `follows`-Zeile weglassen, dann
bringt der Dienst sein eigenes nixpkgs mit.

Optionen: `enable`, `package`, `address`, `port`, `dataDir`, `users`,
`mailFrom`, `baseUrl`, `sendmailPath`, `user`, `group`, `openFirewall`.
`users` darf nicht leer sein. `baseUrl` bestimmt die Adresse in den
Login-Links; ohne Angabe wird sie aus dem Request abgeleitet, was hinter
nginx mit `recommendedProxySettings` (oder gesetztem `Host`-Header)
funktioniert.

Der Dienst läuft als eigener Systembenutzer mit systemd-Härtungen und darf
nur in `dataDir` und in die Mail-Queue schreiben. Eine bewusste Grenze: der
sendmail-Wrapper des MTAs ist setuid/setgid, deshalb kommt der Dienst ohne
`NoNewPrivileges` und ohne seccomp-Filter aus – jede dieser Optionen würde
den Wrapper wirkungslos machen und den Mailversand brechen.

### Anmeldung und Sicherheit

Keine Passwörter: Auf der Login-Seite gibt man seine E-Mail-Adresse an, und
wenn sie in `users` steht, kommt eine Mail mit einem Link, der anmeldet. Das
Token dahinter ist ein HMAC über die Adresse mit einem Schlüssel, den der
Server beim ersten Start in `<Datenverzeichnis>/.secret` ablegt – der Server
hält keine Sessions, ein Neustart wirft niemanden hinaus, und das Token läuft
bewusst nie ab. Konsequenzen, die man kennen sollte:

* Wer das Postfach einer eingetragenen Adresse lesen kann, kann sich
  anmelden – auch über eine alte Login-Mail im Archiv. (Das ist bei jedem
  „Passwort vergessen“-Ablauf genauso.)
* Abmelden einer einzelnen Person: Adresse aus `users` nehmen, ihr Token ist
  sofort ungültig. `.secret` löschen meldet alle ab.
* Der Login-Endpunkt antwortet für bekannte und unbekannte Adressen gleich
  und verschickt pro Adresse höchstens eine Mail pro Minute.

Das Token steht im Link hinter `#` (erreicht also nie Server- oder
Proxy-Logs) und wandert dann in den Local Storage des Browsers. Über die
Verbindung geht es bei jeder Anfrage mit – **die App gehört deshalb hinter
TLS**. Die Voreinstellung `address = "127.0.0.1"` erwartet genau das: einen
Reverse-Proxy davor.

### Umstieg von der Ein-Benutzer-Version

Liegen noch JSON-Dateien direkt im Datenverzeichnis und existiert für die
erste Adresse aus `users` noch kein Unterverzeichnis, verschiebt der Server
die Dateien beim Start dorthin – der Altbestand gehört danach der ersten
Nutzerin der Liste.

### Sicherung

Das Datenverzeichnis ist ein Verzeichnis mit Textdateien – ein `git init` darin
und ein regelmäßiges `git commit -am backup` (oder das übliche Backup) reicht
völlig.

## Bedienung

**Erfassen** – der Ablauf läuft ohne Maus durch: `n` öffnet das Formular, der
Fokus steht im Titel, `Enter` springt jeweils ins nächste Feld (in der
Beschreibung `Tab`), `Strg+S` speichert, `Strg+Enter` speichert und legt gleich
den nächsten Eintrag an – Buch und Altersbereich bleiben dabei stehen. `Esc`
bricht ab.

Schlagworte und Buch haben Typeahead. Getippt wird ein Präfix oder ein Stück
aus der Mitte (`kasus` findet `Sprache/Grammatik/Kasus`); die Liste zeigt am
Ende immer auch das gerade Getippte als neues Schlagwort an, damit sichtbar
ist, was `Enter` tun wird. `Esc` schließt die Liste, danach übernimmt `Enter`
den Text wörtlich.

**Suchen** – zuerst die Schlagwortfilter (beliebig viele, kombinierbar) und der
Alterswert, darunter die Volltextsuche über Titel und Beschreibung: mehrere
Wörter sind UND-verknüpft, `"in Anführungszeichen"` bleibt zusammen, Umlaute
sind egal (`marchen`, `maerchen` und `Märchen` finden dasselbe). Die Liste lässt
sich zwischen „nur Titel“ und „mit Angaben“ (Buch, Ort, Schlagworte)
umschalten. Alle Filter stehen in der URL, der Zurück-Button funktioniert also
auch auf dem Handy wie erwartet.

**Tastenkürzel** – auf der Suchseite bekommt bewusst kein Feld automatisch den
Fokus, damit die Buchstabenkürzel sofort greifen: `n` neuer Eintrag, `t`
Schlagwortfilter, `/` Volltextsuche, `v` Ansicht, `?` Hilfe. Steht der Cursor
doch in einem Feld, tun es dieselben Befehle mit Alt (`Alt+N`, `Alt+T`,
`Alt+F`, `Alt+V`, `Alt+H`) – oder `Esc`, das den Fokus wieder freigibt.

Ganz unten steht eine Fußzeile mit der Zahl der Einträge, der angemeldeten
Nutzerin (samt Abmelden-Knopf) und der git-Revision
des laufenden Programms, verlinkt auf den Commit bei GitHub – so lässt sich von
der laufenden Instanz aus nachsehen, welcher Stand da eigentlich läuft.
Versionsnummern gibt es bewusst keine. Beim Nix-Deployment kommt die Revision
aus dem Flake (`self.rev`, bei unsauberem Arbeitsverzeichnis `self.dirtyRev`)
und wird beim Bauen als `_build.py` ins Paket gelegt, denn im Store gibt es
kein `.git`; läuft die App aus einem Arbeitsverzeichnis, liest sie `.git`
selbst. Das Repository steht in `src/ntm/version.py`.

## Tests

```console
$ nix develop
$ pytest                                    # Backend
$ node test/frontend/smoke.mjs              # Frontend
$ nix flake check                           # beides, plus NixOS-Modul
```

**Backend**: die Kernlogik – Tag-Hierarchie und Typeahead
(`tests/test_tags.py`), Altersachse inklusive „Eltern“ (`tests/test_ages.py`),
Suche und Filterkombinationen (`tests/test_query.py`) –, dazu die Ablage samt
Migration (`tests/test_store.py`), die magic-link-Tokens (`tests/test_auth.py`)
und die HTTP-Schnittstelle samt Anmeldung, Mailversand und Trennung der
Nutzerinnen (`tests/test_api.py`). Dieselben Tests laufen beim `nix build` mit.

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

## Lizenz

MIT, siehe [LICENSE](LICENSE).
