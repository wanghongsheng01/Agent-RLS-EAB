#!/bin/bash
# Two further repetitions for GPT-6 and Claude-Opus-5.5 on the core configurations and the attack, scope-ambiguous and
# published-channel questions. Endpoint and key come from LLMHUB_BASE_URL and LLMHUB_API_KEY (never written to disk).
cd "$(dirname "$0")/.."
for m in gpt-6-sol claude-opus-5.5; do
  for r in 1 2; do
    .venv/bin/python -W ignore code/run_pilot.py --models $m --configs E0,E3T,E4M,E7,E8 --doms tpch,ent,tpcds,bird --cats A1,A2,A3,A4,B2,B3 --rep $r --workers 6 --out pilot/sessions_frontier_reps.jsonl > pilot/frontier_${m}_rep$r.log 2>&1 &
  done
done
wait
echo FRDONE >> pilot/frontier_gpt-6-sol_rep1.log
