#!/bin/bash
# Database placement in the agent loop: PostgreSQL 16 row-level security (E5P) on TPC-H and the production policy
# model, main grid, three repetitions. Requires the databases built by code/native_rls.py.
cd "$(dirname "$0")/.."
export DAILY_CAP=15
for r in 0 1 2; do
  .venv/bin/python -W ignore code/run_pilot.py --models ds-flash,glm-air,kimi-k2.6 --configs E5P --doms tpch,ent --rep $r --workers 2 --out pilot/sessions_e5p.jsonl > pilot/e5p_rep$r.log 2>&1 &
done
wait
echo E5PDONE >> pilot/e5p_rep0.log
