#!/bin/bash
# Data-independent non-Truman check (E3D) on the main grid, three repetitions.
cd "$(dirname "$0")/.."
export DAILY_CAP=15
for r in 0 1 2; do
  .venv/bin/python -W ignore code/run_pilot.py --models ds-flash,glm-air,kimi-k2.6 --configs E3D --doms tpch,ent,tpcds,bird --rep $r --workers 2 --out pilot/sessions_e3d.jsonl > pilot/e3d_fill_rep$r.log 2>&1 &
done
wait
echo E3DDONE >> pilot/e3d_rep0.log
