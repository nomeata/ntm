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
  revision ? "",
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
      ../LICENSE
      ../src
      ../tests
    ];
  };

  # Im Store gibt es kein .git – die Revision kommt aus dem Flake.
  postPatch = ''
    echo 'REVISION = "${revision}"' > src/ntm/_build.py
  '';

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
