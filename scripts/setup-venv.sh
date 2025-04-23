#!/bin/bash
set -e;

test -d venv || virtualenv venv
touch venv/touchfile
