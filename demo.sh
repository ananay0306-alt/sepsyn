#!/usr/bin/env bash
# A seven-beat live demo of sepsyn. Run it in front of someone.
#
#   ./demo.sh              pause between beats, so you can talk
#   NOPAUSE=1 ./demo.sh    run straight through
set -u
cd "$(dirname "$0")"
PY=../.venv/bin/python

b()  { printf '\n\033[1;36m%s\033[0m\n\033[2m%s\033[0m\n\n' "$1" "$2"; }
say() { printf '\033[1;33m>> %s\033[0m\n' "$1"; }
run() { printf '\033[2m$ %s\033[0m\n' "$*"; "$@" 2>/dev/null; }
pause() { [ "${NOPAUSE:-0}" = 1 ] || { printf '\n\033[2m[enter]\033[0m'; read -r _; }; }

b "1. It shows its work" \
  "Not just an answer. The rule that produced the answer, and the numbers it tested."
run $PY -m sepsyn.cli --feed "Benzene:60,Toluene:40" --T 298.15 \
    --light-key Benzene --heavy-key Toluene
say "R-01 fired. You can see the relative volatility it tested: 2.52."
pause

b "2. Every choice is labelled: evidence, or just convention" \
  "This is the one that matters. Unrecorded choices caused a 58% disagreement."
run $PY -m sepsyn.cli --feed "Benzene:60,Toluene:40" --T 298.15 --design \
    --light-key Benzene --heavy-key Toluene | grep -A1 "  step 2" | grep -v "^--$"
say "'[by default]' means nobody proved it. That is a different claim from '[decided]'."
pause

b "3. The hidden assumption that costs money" \
  "Feed thermal condition, q. Same mixture, same purity, only the feed changes."
say "As the feed arrives (cold, q = 1.30):"
run $PY -m sepsyn.cli --feed "Benzene:60,Toluene:40" --T 298.15 --design \
    --light-key Benzene --heavy-key Toluene | grep -E "feed  |cheapest"
say "Preheated to boiling (q = 1.00):"
run $PY -m sepsyn.cli --feed "Benzene:60,Toluene:40" --T 298.15 --design \
    --light-key Benzene --heavy-key Toluene --feed-q 1.0 | grep -E "feed  |cheapest"
say "329,276 -> 291,331 dollars a year. 12%, from an assumption people leave unwritten."
pause

b "4. A rule firing on evidence, not convention" \
  "Shrink the column. Below 0.6 m a tray will not fit through a manway."
run $PY -m sepsyn.cli --feed "Benzene:6,Toluene:4" --T 298.15 --design \
    --light-key Benzene --heavy-key Toluene | grep -A4 "  step 24" | grep -v "^--$"
say "'[decided, E-24b]' -- proven, with the rule id you can go read."
pause

b "5. It knows what it cannot do" \
  "Ethanol and water form an azeotrope. No column of any size separates them."
run $PY -m sepsyn.cli --feed "Ethanol:50,Water:50" --T 298.15 \
    --light-key Ethanol --heavy-key Water | grep -E "R-03|VERDICT|CANDIDATES"
say "INFEASIBLE, and it names what to use instead."
pause

b "6. The failure nobody would have noticed" \
  "Water and butanol form two liquid layers. The model behind the numbers assumes one."
run $PY -m sepsyn.cli --feed "Water:50,Butanol:50" --T 330 \
    --light-key Butanol --heavy-key Water | grep -E "R-12|VERDICT|CANDIDATES"
say "Every other error gives you an obviously silly number. This one gives you"
say "a perfectly reasonable design for a separation that will not happen."
pause

b "7. It refuses to guess" \
  "Glycerol boils at 289 C. Does it decompose first? That is not in any database."
run $PY -m sepsyn.cli --feed "Water:60,Glycerol:40" --T 350 --design \
    --light-key Water --heavy-key Glycerol \
    | awk '/R-11/{p=1} p&&/REQUIRES|R-11/{print} /VERDICT|Not designing/{print}' 
say "It stops, and tells you exactly which number to go and find."
pause

b "8. All of it is checked" ""
run $PY -m pytest -q -p no:warnings
