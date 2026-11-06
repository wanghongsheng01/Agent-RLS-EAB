#!/bin/bash
# Prompt ablations (scope stated for Truman / non-Truman gateways; honest raw-SQL description for the mixed deployment).
cd "$(dirname "$0")/.."
export DAILY_CAP=15
.venv/bin/python -W ignore code/run_pilot.py --models ds-flash,kimi-k2.6 --configs E3TP,E3NP,E4MH --doms tpch,ent,tpcds,bird --rep 0 --workers 8 --out pilot/sessions_ablate.jsonl > pilot/ablate.log 2>&1
echo ABLATEDONE >> pilot/ablate.log
