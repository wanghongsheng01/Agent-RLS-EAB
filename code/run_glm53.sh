#!/bin/bash
# GLM-5.3 (frontier tier, via an OpenAI-compatible gateway): one repetition of the full grid.
# The gateway endpoint and key come from LLMHUB_BASE_URL and LLMHUB_API_KEY and are never written to disk.
cd "$(dirname "$0")/.."
.venv/bin/python -W ignore code/run_pilot.py --models glm-5.3 --configs E0,E2,E6,E3T,E3N,E4,E4M,E7,E8 --doms tpch,ent,tpcds,bird --rep 0 --workers 16 --out pilot/sessions_glm53.jsonl > pilot/glm53.log 2>&1
echo GLM53DONE >> pilot/glm53.log
