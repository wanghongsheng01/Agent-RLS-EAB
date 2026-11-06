#!/bin/bash
# Second side run: GLM and Kimi repetitions 1-2 (separate output; the main grid later re-reads them from the LLM cache).
cd "$(dirname "$0")/.."
export DAILY_CAP=15
C=E0,E2,E6,E3T,E3N,E4,E4M,E7,E8
D=tpch,ent,tpcds,bird
for r in 1 2; do
  .venv/bin/python -W ignore code/run_pilot.py --models glm-air,kimi-k2.6 --configs $C --doms $D --rep $r --workers 8 --out pilot/sessions_side2.jsonl > pilot/side2_rep$r.log 2>&1
done
echo SIDE2DONE >> pilot/side2_rep2.log
