# junit2html-simple
[![Pylint](https://github.com/1089pop/junit2html-simple/actions/workflows/pylint.yml/badge.svg)](https://github.com/1089pop/junit2html-simple/actions/workflows/pylint.yml)  
A lightweight, offline-friendly JUnit XML to HTML report generator.

## Overview

This script converts one or more JUnit XML files into a single self-contained HTML report.  
It is designed with **minimal dependencies** so it can be used in air-gapped or restricted environments where installing large Python packages is impractical.

## Features

- Parse multiple JUnit XML files and merge them into one report
- Hierarchical view: **Suite → Class → Test Case**
- Search, filter by status, and sort (status, time, name) without breaking hierarchy
- Click on a test row to toggle error details; collapsed rows look identical to non-detailed rows
- Generates a **single-file HTML** with inline CSS/JS (no internet connection required)

## Dependencies

- [junitparser](https://pypi.org/project/junitparser/) (offline installable via wheel or source)

No other Python packages are required.

## Usage

```bash
python junit2html_simple.py -o report.html TEST-*.xml
