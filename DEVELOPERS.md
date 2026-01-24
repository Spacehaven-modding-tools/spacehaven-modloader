# Developers Setup

## Purpose

This document explains how to set up a development environment for this project to run the program from the source and
to facilitate development.


## Prerequisites

- pyenv (recommended) — used to install and manage Python versions
- virtualenv — used to create an isolated environment for the project
- pip — Python package installer
- Git — to clone the repository


## Cloning the repository

For the remainder of this document, we'll assume you:
- cloned the repository to your local machine
- the working directory is the root of the repository


## Installing pyenv

If you don't have pyenv installed, follow the official instructions for your platform at https://github.com/pyenv/pyenv.

pyenv is a tool that lets you switch between multiple versions of Python.


## Installing Python

This repository contains a `.python-version` file pinning Python to a specific version.
If you don't have the correct version installed, recommend using pyenv to install:

```shell
pyenv install 3.11.9
```


## Setup Virtual Environment

The virtual environment is used to isolate the project's dependencies from your system Python installation.

Create and activate a Python virtual environment:
```
python -m venv venv
source venv/bin/activate
```

In the active environment, Install Python dependencies:
```
pip install -r requirements.txt
```

If developing, install development dependencies:
```
pip install -r requirements-dev.txt
```


## Running the loader

In the active environment, Run the loader:
```
python spacehaven_modloader.py
```

It is possible to avoid activating the virtual environment for future invocations by running the loader with the path
to the Python interpreter in the virtual environment, e.g. `venv/bin/python` command.
