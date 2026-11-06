#!/bin/bash
# Auditor vs. static rule (E7S) on complement differencing (C1) and own-group totals (C2), plus E7S on the original
# differencing and published-channel questions; main grid three repetitions, GPT-6 and Claude one repetition.
cd "$(dirname "$0")/.."
export DAILY_CAP=15
for r in 0 1 2; do
  .venv/bin/python -W ignore code/run_pilot.py --suite suite_x6.json --models ds-flash,glm-air,kimi-k2.6 --configs E3T,E7,E7S,E8 --doms tpch,tpcds,bird --rep $r --workers 4 --out pilot/sessions_x6.jsonl > pilot/x6_rep$r.log 2>&1 &
  .venv/bin/python -W ignore code/run_pilot.py --models ds-flash,glm-air,kimi-k2.6 --configs E7S --doms tpch,tpcds,bird --cats A3,B3 --rep $r --workers 4 --out pilot/sessions_x6s.jsonl > pilot/x6s_rep$r.log 2>&1 &
done
.venv/bin/python -W ignore code/run_pilot.py --suite suite_x6.json --models gpt-6-sol,claude-opus-5.5 --configs E3T,E7,E7S,E8 --doms tpch,tpcds,bird --rep 0 --workers 4 --out pilot/sessions_x6f.jsonl > pilot/x6f.log 2>&1 &
wait
echo X6DONE >> pilot/x6_rep0.log
