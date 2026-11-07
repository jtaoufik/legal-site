#!/bin/bash
# Usage: ./golfbuddy-finalize.sh "<seller name>" "<support email>" "<country>" [YYYY-MM-DD]
# Replaces the Q-054 / Q-084 placeholders in public/golfbuddy/*.html, sets "Last updated", then fails if any placeholder is left.
set -euo pipefail
[ $# -ge 3 ] || { echo "usage: $0 ENTITY EMAIL COUNTRY [DATE]"; exit 2; }
cd "$(dirname "$0")/public/golfbuddy"
DATE="${4:-$(date +%F)}"
for f in *.html; do
  python3 -I - "$f" "$1" "$2" "$3" "$DATE" <<'PY'
import sys,re
f,ent,mail,country,date=sys.argv[1:]
s=open(f).read()
s=s.replace('[TODO Q-054 seller name]',ent).replace('[TODO Q-084 support email]',mail).replace('[TODO Q-054 country of the seller]',country)
s=re.sub(r'Last updated \d{4}-\d{2}-\d{2}','Last updated '+date,s)
open(f,'w').write(s)
PY
done
if grep -n -i -E 'TODO|lorem|<entity>' *.html; then echo "FAIL: placeholder left"; exit 1; fi
grep -q "Last updated $DATE" privacy.html terms.html support.html
grep -qF "Matches may include computer-controlled players." terms.html
echo "OK: GolfBuddy legal pages finalized ($DATE)"
