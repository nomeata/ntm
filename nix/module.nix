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

    passwordFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      example = "/run/secrets/ntm-password";
      description = ''
        Datei, die das Passwort enthält (erste Zeile, ohne Zeilenumbruch nötig).
        Wird über systemd-Credentials eingelesen und landet nicht im Nix-Store.
      '';
    };

    password = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = ''
        Passwort im Klartext.  Bequem, aber es landet im Nix-Store und ist
        damit für alle lokalen Nutzer lesbar – im Zweifel {option}`passwordFile`
        verwenden.
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
        assertion = (cfg.password == null) != (cfg.passwordFile == null);
        message = ''
          services.ntm: genau eine der Optionen `password` und `passwordFile`
          muss gesetzt sein.
        '';
      }
    ];

    warnings = lib.optional (cfg.password != null) ''
      services.ntm.password landet im Nix-Store und ist dort für alle lesbar.
      Besser: services.ntm.passwordFile.
    '';

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
      }
      // lib.optionalAttrs (cfg.password != null) { NTM_PASSWORD = cfg.password; }
      // lib.optionalAttrs (cfg.passwordFile != null) {
        NTM_PASSWORD_FILE = "%d/ntm-password";
      };

      serviceConfig = {
        ExecStart = lib.getExe cfg.package;
        User = cfg.user;
        Group = cfg.group;
        WorkingDirectory = cfg.dataDir;
        Restart = "on-failure";
        RestartSec = 5;

        LoadCredential = lib.mkIf (cfg.passwordFile != null) [
          "ntm-password:${cfg.passwordFile}"
        ];

        # Härtung – der Dienst braucht nur sein Datenverzeichnis.
        # Angelegt wird es über systemd.tmpfiles (siehe oben), damit für jedes
        # dataDir derselbe Weg gilt.
        ReadWritePaths = [ cfg.dataDir ];
        CapabilityBoundingSet = [ "" ];
        DevicePolicy = "closed";
        LockPersonality = true;
        MemoryDenyWriteExecute = true;
        NoNewPrivileges = true;
        PrivateDevices = true;
        PrivateTmp = true;
        PrivateUsers = true;
        ProcSubset = "pid";
        ProtectClock = true;
        ProtectControlGroups = true;
        ProtectHome = true;
        ProtectHostname = true;
        ProtectKernelLogs = true;
        ProtectKernelModules = true;
        ProtectKernelTunables = true;
        ProtectProc = "invisible";
        ProtectSystem = "strict";
        RestrictAddressFamilies = [
          "AF_INET"
          "AF_INET6"
          "AF_UNIX"
        ];
        RestrictNamespaces = true;
        RestrictRealtime = true;
        RestrictSUIDSGID = true;
        SystemCallArchitectures = "native";
        SystemCallFilter = [
          "@system-service"
          "~@privileged"
          "~@resources"
        ];
        UMask = "0077";
      };
    };
  };
}
