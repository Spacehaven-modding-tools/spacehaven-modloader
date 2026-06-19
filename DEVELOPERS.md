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
