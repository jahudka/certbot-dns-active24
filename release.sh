#!/usr/bin/env bash

set -eu

case "${1:-}" in
    major) version_idx=0 ;;
    minor) version_idx=1 ;;
    patch) version_idx=2 ;;
    *)
        echo "Usage: $0 <major|minor|patch>"
        exit 1
    ;;
esac

if [[ "$( git status -uno --porcelain=v1 )" != "" ]]; then
    echo "Working tree is not clean, please commit all changes first"
    exit 1
fi

if [[ ! -d '.venv' ]]; then
    python3 -m venv .venv
    pip3 install -e .
fi

if [[ "$( which python3 )" != "$( pwd )/.venv/bin/python3" ]]; then
    source .venv/bin/activate
fi

IFS=$'\n' version=($( python3 <<EOT
from certbot_dns_active24 import __version__

print(__version__)

version = [int(n) for n in __version__.split('.')]
version[${version_idx}] += 1
version[$(( version_idx + 1 )):] = [0]*$(( 2 - version_idx ))

print('.'.join([str(n) for n in version]))
EOT
))

sed -i '' -e "s/${version[0]}/${version[1]}/g" certbot_dns_active24/__init__.py

git add certbot_dns_active24/__init__.py
git commit -m "Release v${version[1]}"
git tag -s "v${version[1]}" -m "Release v${version[1]}"
git push
git push --tags

mkdir -p dist
rm -rf dist/*

python3 setup.py sdist

pip3 install twine

twine upload --repository certbot-dns-active24 dist/*

echo "Published version ${version[1]}."
