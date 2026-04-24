# Developers Setup

## Purpose

This document explains how to set up a development environment for this project to run the program from the source and
to facilitate development.


## Prerequisites

- git — to clone the repository
- uv — Python package and project manager


## Install uv
`uv` is a project and package manager for Python.
If you don't have uv installed, follow the official instructions for your platform at
https://docs.astral.sh/uv/getting-started/installation/

## Cloning the repository

`git clone` the repository into your Projects folder.

For the remainder of this document, we'll assume the working directory is the root of the repository.

## Installing pyenv

If you don't have pyenv installed, follow the official instructions for your platform at https://github.com/pyenv/pyenv.

pyenv is a tool that lets you switch between multiple versions of Python.


## Installing Python

This repository contains a `.python-version` file pinning Python to a specific version.
`uv` should automaatically install the declared version.

Alternatively, you can manually install python with the uv command:
```shell
uv python install 3.11.9
```

## Set up Virtual Environment

`uv` will create a virtual environment to isolate the project's dependencies from your system Python installation.

Install Python dependencies:
```shell
uv sync --frozen
```


## Running the loader

Run the loader with the command:
```
uv run python spacehaven-modloader.py
```

It is possible to avoid activating the virtual environment for future invocations by running the loader with the path
to the Python interpreter in the virtual environment, e.g. `venv/bin/python` command.


## JAR / AspectJ Mod Internals

This section is for authors of code-injection (JAR/AspectJ) mods, not end users. End users should read [README.md](README.md).

### Where the loader writes `config.json`

`config.json` is always resolved as `<gameDir>/config.json`, where `<gameDir>` is the directory of the detected `spacehaven.jar`. The loader never resolves `config.json` relative to a Steam Workshop content folder, even when the mod itself lives in `steamapps/workshop/content/979110/<id>/`.

### `classPath` injection

When a JAR mod is enabled, the loader inserts the JAR's absolute path (with forward slashes) into `config.json` → `classPath`, immediately before `spacehaven.jar`. AspectJ entries (`aspectjweaver-1.9.19.jar`, `aspectj-1.9.19.jar`) are kept at positions 0 and 1. Existing unrelated entries are preserved in their original order.

### `classPath` cleanup

During mod discovery and before each launch, the loader performs a conservative cleanup of `classPath`:

- Entries under known mod roots (local `mods/` and the Steam Workshop content folder) that no longer correspond to an enabled mod are removed.
- Entries under known mod roots whose file is missing are removed.
- Exact duplicate entries are deduped.
- Entries outside known mod roots are left untouched (manual additions are preserved).
- If `config.json` is missing or `classPath` is not a list, cleanup is skipped.

### Asset resolution for JAR mods

Java mods that need external assets should not assume a fixed `SpaceHaven/mods/<ModName>` layout, because the same mod may also be installed from Workshop. The two supported patterns are:

1. **Bundle assets inside the JAR** and read them via `getResource()` / `getResourceAsStream()`.
2. **Resolve files relative to the JAR's own location** using `getProtectionDomain().getCodeSource().getLocation()`. Example:

   ```java
   URL jarUrl = MyMod.class.getProtectionDomain()
       .getCodeSource()
       .getLocation();
   Path modDir = Paths.get(jarUrl.toURI()).getParent();
   Path config = modDir.resolve("mystuff/config.json");
   ```

Either pattern works equally well for local and Workshop installs and avoids relying on a global classpath registry.
