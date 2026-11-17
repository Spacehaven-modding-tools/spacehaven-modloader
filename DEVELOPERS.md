# Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and run these commands from the repository root. The repository pins Python through `.python-version`.

```powershell
uv sync --locked
uv run --locked python spacehaven-modloader.py
```

## Tests

```powershell
uv run --locked ruff check loader ui tests generate_nsis_filelist.py spacehaven-modloader.py tools
uv run --locked python -m unittest discover -s tests -v
```

The Windows CI runs the DateFix tests on Temurin 25 and 27. To run them locally, put `javac` on PATH and set `SHL_TEST_JAVA25`, `SHL_TEST_JAVA27`, and `SHL_TEST_WEAVER` to the two verified Java executables and the AspectJ 1.9.27 JAR. Without those paths, the corresponding tests are skipped.

## Build

```powershell
uv run --locked python tools/build_frozen.py
```

The frozen build goes to `build/spacehaven-modloader`. On Windows, create `dist/`, run `uv run --locked python generate_nsis_filelist.py`, then run `makensis installer.nsi` to build the installer.

## Rebuild DateFix

Put a JDK with `javac --release 8` support on PATH. Run `uv run --locked python tools/date_text_fix/build_patch.py` to check that the build matches the pinned JAR. After changing the aspect or its descriptors, use `--update-hash` and run the weaving tests on both JVMs.

## Test a Release Build

Use an isolated copy of Space Haven 1.0.4. Launch once with the bundled Java runtime and no mods. Then launch with Temurin 25 or 27, open **Load Game**, and check the timestamp before the AM/PM marker. Repeat with an XML mod and a JAR mod. Report the loader version, game build, selected runtime, mods, and steps to reproduce.

Check an exported diagnostics ZIP for local paths or account identifiers before sharing it.
