#!/bin/bash
# External verifier and output guard (GPT-6) for the DS-flash and Kimi agents: E2X and E6X, one repetition.
cd "$(dirname "$0")/.."
export DAILY_CAP=15
.venv/bin/python -W ignore code/run_pilot.py --models ds-flash,kimi-k2.6 --configs E2X,E6X --doms tpch,ent,tpcds,bird --rep 0 --workers 8 --out pilot/sessions_external.jsonl > pilot/external.log 2>&1
echo EXTDONE >> pilot/external.log
