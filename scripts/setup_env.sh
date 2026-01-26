#!/usr/bin/env bash
set -euo pipefail

PYTHON=${1-python}
VENV_DIR=${2-.venv}

echo "Creating virtual environment in ${VENV_DIR} using ${PYTHON}"
${PYTHON} -m venv "${VENV_DIR}"

VENV_PY="${VENV_DIR}/bin/python"
if [ ! -x "${VENV_PY}" ]; then
  echo "virtualenv python not found at ${VENV_PY}" >&2
  exit 1
fi

echo "Upgrading pip and installing requirements.txt"
"${VENV_PY}" -m pip install --upgrade pip setuptools wheel
"${VENV_PY}" -m pip install -r "$(dirname "$0")/../requirements.txt"

echo "Setup complete. To run the app (bash):"
echo "  ${VENV_PY} ../app.py"
