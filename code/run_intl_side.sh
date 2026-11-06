#!/bin/bash
# Side runs for run_intl.sh: same grid from the other end (out name contains "side"); score.iter_sessions
# deduplicates, and sessions both runs reach are answered from the request cache.
cd "$(dirname "$0")/.."
for m in gpt-6-sol claude-opus-5.5; do
  .venv/bin/python -W ignore code/run_pilot.py --models $m --configs E0,E2,E6,E3T,E3N,E4,E4M,E7,E8 --doms tpch,ent,tpcds,bird --rep 0 --workers 10 --out pilot/sessions_${m}_side.jsonl > pilot/${m}_side.log 2>&1 &
done
wait
