{
  description = "ntm – Verwaltung von Therapiematerialien";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        rec {
          ntm = pkgs.python3Packages.callPackage ./nix/package.nix {
            revision = self.rev or self.dirtyRev or "";
          };
          default = ntm;
        }
      );

      overlays.default = final: _prev: {
        ntm = final.python3Packages.callPackage ./nix/package.nix {
          revision = self.rev or self.dirtyRev or "";
        };
      };

      nixosModules.default = import ./nix/module.nix { inherit self; };
      nixosModules.ntm = self.nixosModules.default;

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${nixpkgs.lib.getExe self.packages.${system}.default}";
          meta.description = "ntm starten";
        };
      });

      checks = forAllSystems (
        system:
        {
          package = self.packages.${system}.default;
          frontend = nixpkgs.legacyPackages.${system}.callPackage ./nix/frontend-test.nix { };
        }
        // nixpkgs.lib.optionalAttrs (nixpkgs.lib.hasSuffix "-linux" system) {
          # Baut die systemd-Unit einer Minimalkonfiguration – prüft also, dass
          # das Modul samt serviceConfig durchläuft, ohne ein ganzes System zu
          # bauen.
          module =
            (nixpkgs.lib.nixosSystem {
              modules = [
                self.nixosModules.default
                {
                  nixpkgs.hostPlatform = system;
                  boot.loader.grub.enable = false;
                  fileSystems."/" = {
                    device = "/dev/null";
                    fsType = "ext4";
                  };
                  system.stateVersion = "25.11";
                  services.nullmailer = {
                    enable = true;
                    config.me = "example.org";
                  };
                  services.ntm = {
                    enable = true;
                    port = 8123;
                    users = [ "anna@example.org" ];
                    mailFrom = "ntm@example.org";
                  };
                }
              ];
            }).config.systemd.units."ntm.service".unit;
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3.withPackages (ps: [
            ps.fastapi
            ps.uvicorn
            ps.markdown-it-py
            ps.linkify-it-py
            ps.pytest
            ps.httpx
          ]);
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.nixfmt
              pkgs.nodejs # nur für den Frontend-Test, siehe test/frontend
            ];
            shellHook = ''
              export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
              export NTM_DATA_DIR="''${NTM_DATA_DIR:-$PWD/data}"
              echo "ntm-Entwicklungsumgebung – Start: python -m ntm"
            '';
          };
        }
      );

      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixfmt);
    };
}
