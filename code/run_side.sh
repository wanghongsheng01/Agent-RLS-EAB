#!/bin/bash
# Parallel side runs (separate output files; the main grid later re-reads them from the LLM cache).
cd "$(dirname "$0")/.."
export DAILY_CAP=15
C=E0,E2,E6,E3T,E3N,E4,E4M,E7,E8
D=tpch,ent,tpcds,bird
.venv/bin/python -W ignore code/run_pilot.py --models ds-pro --configs $C --doms $D --rep 0 --workers 10 --out pilot/sessions_dspro.jsonl > pilot/side_dspro.log 2>&1 &
( for r in 1 2; do .venv/bin/python -W ignore code/run_pilot.py --models ds-flash --configs $C --doms $D --rep $r --workers 10 --out pilot/sessions_dsf.jsonl > pilot/side_dsf_rep$r.log 2>&1; done ) &
wait
echo SIDEDONE >> pilot/side_dspro.log
