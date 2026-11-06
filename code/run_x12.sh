#!/bin/bash
# Follow-up experiments: E4MT (truthful raw-SQL description without the policy) on the ablation models, and E8P
# (coverage note reworded so that it shares no words with the answer format) on the main grid, three repetitions.
cd "$(dirname "$0")/.."
export DAILY_CAP=15
.venv/bin/python -W ignore code/run_pilot.py --models ds-flash,kimi-k2.6 --configs E4MT --doms tpch,ent,tpcds,bird --rep 0 --workers 8 --out pilot/sessions_x1.jsonl > pilot/x1.log 2>&1 &
for r in 0 1 2; do
  .venv/bin/python -W ignore code/run_pilot.py --models ds-flash,glm-air,kimi-k2.6 --configs E8P --doms tpch,ent,tpcds,bird --rep $r --workers 6 --out pilot/sessions_x2.jsonl > pilot/x2_rep$r.log 2>&1 &
done
wait
echo X12DONE >> pilot/x1.log
