#!/bin/bash
# Paste cosim_test.py into the guest's /tmp through the QEMU console (no scp, no clipboard).
# The guest root is a RAM disk, so this is needed after every boot. Run it on the laptop once you are
# logged in at the guest prompt (the tmux session must not be attached in a way that steals the keys).
# Usage: ./paste_to_guest.sh [tmux-session, default qemu]
set -euo pipefail
SESSION=${1:-qemu}
SRC=$(cd "$(dirname "$0")" && pwd)/cosim_test.py
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
tmux send-keys -t "$SESSION" 'rm -f /tmp/cosim_test.py' Enter; sleep 2
split -l 18 -d "$SRC" "$TMP/part_"          # 18-line chunks: the slow guest drops characters on big pastes
for f in "$TMP"/part_*; do
  { echo "cat >> /tmp/cosim_test.py <<'EOF_CT'"; cat "$f"; echo "EOF_CT"; } > "$f.paste"
  tmux load-buffer -b ct "$f.paste"; tmux paste-buffer -b ct -t "$SESSION"; sleep 6
done
tmux send-keys -t "$SESSION" 'wc -l /tmp/cosim_test.py; sha256sum /tmp/cosim_test.py' Enter
echo "laptop : $(sha256sum "$SRC")"
echo "guest  : (see the console) must show 108 lines and the same sha256"
