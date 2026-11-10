#!/bin/bash
# Run a command with the gateway and Volcano Ark endpoints in its environment; keys are read from the macOS keychain at
# run time, exported only to this process tree, and never printed or written to disk.
export LLMHUB_BASE_URL="${LLMHUB_BASE_URL:?set the OpenAI-compatible gateway endpoint}"
export LLMHUB_API_KEY="$(security find-generic-password -s llm-gateway -w)"
export LLMHUB_QWEN_KEY="$(security find-generic-password -s llm-gateway-qwen-thinking -w)"
export ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
export ARK_API_KEY="$(security find-generic-password -s volc-ark-kimi -w)"
exec "$@"
