{ self }:
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.ntm;
in
{
  options.services.ntm = {
    enable = lib.mkEnableOption "ntm, die Verwaltung von Therapiematerialien";

    package = lib.mkOption {
      type = lib.types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      defaultText = lib.literalExpression "ntm.packages.\${system}.default";
      description = "Zu verwendendes ntm-Paket.";
    };

    address = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1";
      description = ''
        Adresse, auf der gelauscht wird.  Die Voreinstellung erwartet einen
        Reverse-Proxy davor; für den direkten Zugriff aus dem Netz "0.0.0.0".
      '';
    };

    port = lib.mkOption {
      type = lib.types.port;
      default = 8123;
      description = "Port des HTTP-Servers.";
    };

    dataDir = lib.mkOption {
      type = lib.types.path;
      default = "/var/lib/ntm";
      description = ''
        Verzeichnis mit einer JSON-Datei pro Eintrag.  Wird angelegt, falls es
        noch nicht existiert.
      '';
    };

    users = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      example = [
        "anna@example.org"
        "bea@example.org"
      ];
      description = ''
        E-Mail-Adressen der Nutzerinnen.  Angemeldet wird per Link in einer
        E-Mail; jede Adresse bekommt ihr eigenes Unterverzeichnis im
        Datenverzeichnis.  Die *erste* Adresse erbt beim Umstieg einen
        etwaigen Altbestand aus der Ein-Benutzer-Zeit.
      '';
    };

    mailFrom = lib.mkOption {
      type = lib.types.str;
      example = "ntm@example.org";
      description = "Absender der Login-Mails.";
    };

    baseUrl = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "https://material.example.org";
      description = ''
        Öffentliche Adresse der App, für die Links in den Login-Mails.
        Ohne Angabe wird sie aus dem Request abgeleitet (Host bzw.
        X-Forwarded-Proto/-Host des Reverse-Proxys).
      '';
    };

    sendmailPath = lib.mkOption {
      type = lib.types.str;
      default = "/run/wrappers/bin/sendmail";
      description = ''
        sendmail-Programm für den Mailversand.  Die Vorgabe passt zu jedem
        lokalen MTA mit sendmail-Wrapper, etwa {option}`services.nullmailer`.
      '';
    };

    user = lib.mkOption {
      type = lib.types.str;
      default = "ntm";
      description = "Systembenutzer, unter dem der Dienst läuft.";
    };

    group = lib.mkOption {
      type = lib.types.str;
      default = "ntm";
      description = "Gruppe des Dienstes.";
    };

    openFirewall = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Den konfigurierten Port in der Firewall öffnen.";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = cfg.users != [ ];
        message = "services.ntm: `users` darf nicht leer sein – ohne Nutzerliste liefe die App ungeschützt.";
      }
    ];

    users.users = lib.mkIf (cfg.user == "ntm") {
      ntm = {
        isSystemUser = true;
        group = cfg.group;
        home = cfg.dataDir;
      };
    };

    users.groups = lib.mkIf (cfg.group == "ntm") { ntm = { }; };

    systemd.tmpfiles.rules = [
      "d ${cfg.dataDir} 0750 ${cfg.user} ${cfg.group} - -"
    ];

    networking.firewall.allowedTCPPorts = lib.mkIf cfg.openFirewall [ cfg.port ];

    systemd.services.ntm = {
      description = "ntm – Verwaltung von Therapiematerialien";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];

      environment = {
        NTM_DATA_DIR = cfg.dataDir;
        NTM_HOST = cfg.address;
        NTM_PORT = toString cfg.port;
        NTM_USERS = lib.concatStringsSep "," cfg.users;
        NTM_MAIL_FROM = cfg.mailFrom;
        NTM_SENDMAIL = cfg.sendmailPath;
      }
      // lib.optionalAttrs (cfg.baseUrl != null) { NTM_BASE_URL = cfg.baseUrl; };

      serviceConfig = {
        ExecStart = lib.getExe cfg.package;
        User = cfg.user;
        Group = cfg.group;
        WorkingDirectory = cfg.dataDir;
        Restart = "on-failure";
        RestartSec = 5;

        # Härtung – der Dienst braucht sein Datenverzeichnis und den Weg zur
        # Mail-Queue.  Angelegt wird das Datenverzeichnis über systemd.tmpfiles
        # (siehe oben), damit für jedes dataDir derselbe Weg gilt.
        #
        # Bewusste Grenze: Die Login-Mails gehen über den sendmail-Wrapper des
        # lokalen MTAs, und der ist setuid/setgid (bei nullmailer: um in die
        # Queue schreiben zu dürfen).  Deshalb kein NoNewPrivileges – und auch
        # keine der seccomp-Optionen (SystemCallFilter, RestrictNamespaces,
        # Private*/Protect*-Kernel-Optionen …), denn jede davon erzwingt bei
        # gesetztem User= wiederum NoNewPrivileges.
        ReadWritePaths = [
          cfg.dataDir
          "-/var/spool/nullmailer"
        ];
        CapabilityBoundingSet = [ "" ];
        DevicePolicy = "closed";
        NoNewPrivileges = false;
        PrivateTmp = true;
        ProcSubset = "pid";
        ProtectControlGroups = true;
        ProtectHome = true;
        ProtectProc = "invisible";
        ProtectSystem = "strict";
        UMask = "0077";
      };
    };
  };
}
