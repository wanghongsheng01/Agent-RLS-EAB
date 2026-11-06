#!/bin/bash
# Expanded grid: 4 domains x 9 configs; 3 vendors x 3 reps, then DeepSeek-V4-pro x 1 rep. Resumable.
cd "$(dirname "$0")/.."
export DAILY_CAP=15
C=E0,E2,E6,E3T,E3N,E4,E4M,E7,E8
D=tpch,ent,tpcds,bird
for r in 0 1 2; do
  .venv/bin/python -W ignore code/run_pilot.py --models ds-flash,glm-air,kimi-k2.6 --configs $C --doms $D --rep $r --workers 10 > pilot/grid_rep$r.log 2>&1
done
.venv/bin/python -W ignore code/run_pilot.py --models ds-pro --configs $C --doms $D --rep 0 --workers 10 > pilot/grid_dspro.log 2>&1
echo ALLDONE >> pilot/grid_dspro.log
