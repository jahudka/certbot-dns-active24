#!/usr/bin/env bash

set -eu

if [[ "$( git status -uno --porcelain=v1 )" != "" ]]; then
    echo "Working tree is not clean, please commit all changes first"
    exit 1
fi

if ! git describe --exact-match --tags 2&>/dev/null; then
    echo "Please tag the current package version"
    exit 1
fi

if [[ ! -d '.venv' ]]; then
    python3 -m venv .venv
    pip3 install -e .
fi

if [[ "$( which python3 )" != "$( pwd )/.venv/bin/python3" ]]; then
    source .venv/bin/activate
fi

git push
git push --tags

rm -rf dist src/*.egg-info
pip3 install --upgrade build twine
python3 -m build
python3 -m twine upload --repository certbot-dns-active24 dist/*

echo "Published version $( git describe --exact-match --tags )."
