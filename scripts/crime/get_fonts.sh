#!/usr/bin/env bash
# Download the fonts of the case-file videos (npm packages, pinned in scripts/crime/fonts.json for the channel's
# language in prompts/channel.json) into <dir>/<package> for scripts/crime/fonts.py.
# Usage: scripts/crime/get_fonts.sh <dir>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
PKGS=$(python3 -c "import json;l=json.load(open('$HERE/../../prompts/channel.json'))['lang'];print(' '.join(json.load(open('$HERE/fonts.json'))[l]['packages']))")
mkdir -p "$1" && cd "$1"
for spec in $PKGS; do
  name=${spec%@*}; dir=${name##*/}
  [ -f "$dir/index.css" ] && continue
  npm pack -q "$spec" >/dev/null
  tgz=$(ls -t *.tgz | head -1)
  mkdir -p "$dir" && tar -xzf "$tgz" -C "$dir" --strip-components=1 && rm -f "$tgz"
done
ls "$1"
