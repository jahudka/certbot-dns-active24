#!/usr/bin/env bash

set -eu

if [[ "$( git status -uno --porcelain=v1 )" != "" ]]; then
    echo "Working tree is not clean, please commit all changes first"
    exit 1
fi

if ! git describe --exact-match --tags 2>/dev/null; then
    echo "Please tag the current package version"
    exit 1
fi

if [[ ! -d '.venv' ]]; then
    python -m venv .venv
    source .venv/bin/activate
    pip install -e .
fi

if [[ "$( which python )" != "$( pwd )/.venv/bin/python" ]]; then
    source .venv/bin/activate
fi

git push
git push --tags

rm -rf dist src/*.egg-info
pip install --upgrade build twine
python -m build
python -m twine upload --repository certbot-dns-active24 dist/*

echo "Published version $( git describe --exact-match --tags )."
