#!/bin/bash
# GPT-6-sol and Claude-Opus-5.5 (international frontier models, via an OpenAI-compatible gateway): one repetition
# of the full grid each. The gateway endpoint and key come from LLMHUB_BASE_URL and LLMHUB_API_KEY and are never
# written to disk.
cd "$(dirname "$0")/.."
for m in gpt-6-sol claude-opus-5.5; do
  .venv/bin/python -W ignore code/run_pilot.py --models $m --configs E0,E2,E6,E3T,E3N,E4,E4M,E7,E8 --doms tpch,ent,tpcds,bird --rep 0 --workers 12 --out pilot/sessions_$m.jsonl > pilot/$m.log 2>&1 &
done
wait
echo INTLDONE >> pilot/gpt-6-sol.log
