{
  lib,
  buildPythonApplication,
  setuptools,
  fastapi,
  uvicorn,
  markdown-it-py,
  linkify-it-py,
  pytestCheckHook,
  httpx,
}:

buildPythonApplication {
  pname = "ntm";
  version = "0.1.0";
  pyproject = true;

  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../pyproject.toml
      ../README.md
      ../src
      ../tests
    ];
  };

  build-system = [ setuptools ];

  dependencies = [
    fastapi
    uvicorn
    markdown-it-py
    linkify-it-py
  ];

  nativeCheckInputs = [
    pytestCheckHook
    httpx
  ];

  pythonImportsCheck = [ "ntm" ];

  meta = {
    description = "Verwaltung von Therapiematerialien";
    mainProgram = "ntm";
    license = lib.licenses.mit;
    platforms = lib.platforms.unix;
  };
}
