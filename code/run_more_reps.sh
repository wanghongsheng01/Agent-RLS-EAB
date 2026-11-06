#!/bin/bash
# Two further repetitions for GLM-5.3 and DeepSeek-V4-pro on the core configurations and the attack, scope-ambiguous
# and published-channel questions (as for GPT-6 and Claude). Gateway endpoint and key from LLMHUB_* only.
cd "$(dirname "$0")/.."
export DAILY_CAP=15
for m in glm-5.3 ds-pro; do
  for r in 1 2; do
    .venv/bin/python -W ignore code/run_pilot.py --models $m --configs E0,E3T,E4M,E7,E8 --doms tpch,ent,tpcds,bird --cats A1,A2,A3,A4,B2,B3 --rep $r --workers 6 --out pilot/sessions_more_reps.jsonl > pilot/more_${m}_rep$r.log 2>&1 &
  done
done
wait
echo MRDONE >> pilot/more_glm-5.3_rep1.log
