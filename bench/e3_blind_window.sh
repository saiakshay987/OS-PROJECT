#!/bin/sh
# bench/e3_blind_window.sh [broker] — E3: what does a model swap cost?                                   Owner: P2
# Runs the daemon on THIS machine for every combination and appends one row per run to results/e3_blind_window.csv.
# Needs: a running broker, models/pool signed, keys/pool_pub.pem, models/test_encoded.npz. Repeat the key rows in QEMU by hand.
B=${1:-127.0.0.1}; SECS=${SECS:-30}; mkdir -p results
for swap in ${SWAPS:-34 207 550}; do for fb in ${FALLBACKS:-arm hold open}; do for rate in ${RATES:-100 500 1500}; do
  python3 app/appliance/idsd.py --broker "$B" --factory models/pool --pubkey keys/pool_pub.pem --pool /tmp/e3pool --block log \
      --rotate fixed --rotate-s 5 --swap-ms "$swap" --fallback "$fb" --seed 1 > /tmp/e3_idsd.log 2>&1 &
  pid=$!; sleep 3
  python3 app/laptop/replay.py --broker "$B" --n $((rate * SECS)) --rate "$rate" --csv results/e3_blind_window.csv \
      --label "swap${swap}_${fb}_rate${rate}" | sed -n 2p
  kill $pid; wait $pid 2>/dev/null
done; done; done
# baseline without rotation, for the recall and latency you lose nothing against:
python3 app/appliance/idsd.py --broker "$B" --factory models/pool --pubkey keys/pool_pub.pem --pool /tmp/e3pool --block log --rotate off --seed 1 > /tmp/e3_idsd.log 2>&1 &
pid=$!; sleep 3; python3 app/laptop/replay.py --broker "$B" --n $((500 * SECS)) --rate 500 --csv results/e3_blind_window.csv --label "no_rotation_rate500" | sed -n 2p; kill $pid
echo "rows in results/e3_blind_window.csv"
