#!/usr/bin/env python3
# Cut the big ids_cosim.vcd down to the first inference and rebase time to 0, so GTKWave opens on the action.
# Usage: trim_vcd.py ids_cosim.vcd one_inference.vcd [length_ms=20.04]
# Window start = 10 us before the first AXI write (the first record's first input word).
import re, sys
src, dst = sys.argv[1], sys.argv[2]
length_ps = int(float(sys.argv[3] if len(sys.argv) > 3 else 20.04) * 1e9)
L = open(src).read().split('\n')
end = next(i for i, l in enumerate(L) if l.startswith('$enddefinitions'))
hdr, ids, sc = L[:end + 1], {}, []
for l in hdr:
    if l.startswith('$scope'): sc.append(l.split()[2])
    elif l.startswith('$upscope'): sc.pop()
    elif l.startswith('$var'): p = l.split(); ids[p[3]] = '/'.join(sc) + '/' + p[4]
awvalid = next(i for i, n in ids.items() if n.endswith('/awvalid'))
t, ev = 0, []
for l in L[end + 1:]:
    if l.startswith('#'): t = int(l[1:]); continue
    m = re.match(r'^([01])(\S+)$', l) or re.match(r'^(b[01]+) (\S+)$', l)
    if m and m.group(2) in ids: ev.append((t, m.group(2), (m.group(1) + m.group(2)) if len(m.group(1)) == 1 else (m.group(1) + ' ' + m.group(2))))
t_first = next(t for t, i, line in ev if i == awvalid and line.startswith('1'))
T0, T1 = t_first - 10_000_000, t_first - 10_000_000 + length_ps
state, out_ev = {}, []
for t, i, line in ev:
    if t <= T0: state[i] = line
    elif t <= T1: out_ev.append((t - T0, line))
out = hdr + ['', '$dumpvars'] + [state[i] for i in ids if i in state] + ['$end']
cur = None
for t, line in out_ev:
    if t != cur: out.append('#%d' % t); cur = t
    out.append(line)
out.append('#%d' % (T1 - T0))
open(dst, 'w').write('\n'.join(out) + '\n')
print('window starts at %.3f s of simulated time; %d events kept' % (T0 / 1e12, len(out_ev)))
