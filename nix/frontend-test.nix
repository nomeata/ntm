{
  lib,
  stdenvNoCC,
  nodejs,
  fetchNpmDeps,
  npmHooks,
}:

# Lädt src/ntm/static/app.js in eine jsdom-Seite und spielt die Bedienung
# durch (siehe test/frontend/smoke.mjs).  Die App selbst hat weiterhin keine
# JavaScript-Abhängigkeiten – jsdom steckt allein in diesem Test.

stdenvNoCC.mkDerivation {
  name = "ntm-frontend-test";

  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../src/ntm/static
      ../test/frontend
    ];
  };

  sourceRoot = "source/test/frontend";

  nativeBuildInputs = [
    nodejs
    npmHooks.npmConfigHook
  ];

  npmDeps = fetchNpmDeps {
    name = "ntm-frontend-test-npm-deps";
    src = ../test/frontend;
    hash = "sha256-1kpNsvs20iWdT5+AcBDxMSBGCOmppnGfgoj9ciRFNY0=";
  };

  buildPhase = ''
    runHook preBuild
    node smoke.mjs
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    touch $out
    runHook postInstall
  '';
}
