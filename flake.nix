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
          ntm = pkgs.python3Packages.callPackage ./nix/package.nix { };
          default = ntm;
        }
      );

      overlays.default = final: _prev: {
        ntm = final.python3Packages.callPackage ./nix/package.nix { };
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

      checks = forAllSystems (system: {
        package = self.packages.${system}.default;
      });

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
