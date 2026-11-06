"""Cached OpenAI-compatible client for the Agent-RLS pilot (OpenAI-compatible, with native tool calling).

Every call records latency, tokens and list-price dollars; the cache key includes the full request body (messages,
tools) and a repeat index `rep`; a per-model daily spend guard keeps this session's share of the shared
$20/model/day cap. Keys are read from the shared file at run time and never copied. Only synthetic/public benchmark
text is sent to the vendors.
"""
import hashlib, json, os, time, threading, datetime
import requests

ROOT = os.environ.get("AGENT_RLS_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = json.load(open(os.environ["LLM_KEYS_JSON"])) if os.environ.get("LLM_KEYS_JSON") else {}
CACHE_DIR = os.path.join(HERE, "cache")
LOG = os.path.join(CACHE_DIR, "usage.log")
os.makedirs(CACHE_DIR, exist_ok=True)

MODELS = {"ds-flash": ("deepseek", "deepseek-flash"), "ds-pro": ("deepseek", "deepseek-v4-pro"),
          "glm-air": ("glm2", "glm-4.5-air"), "kimi-k2.6": ("kimi", "kimi-k2.6"),
          "gpt-6-sol": ("llmhub", "gpt-6-sol"), "glm-5.3": ("llmhub", "glm-5.3"),
          "claude-opus-5.5": ("llmhub", "claude-opus-5-5")}
OFF = {"thinking": {"type": "disabled"}}
FIXED = {"ds-flash": OFF, "ds-pro": OFF, "glm-air": OFF, "kimi-k2.6": {**OFF, "temperature": 0.6}, "glm-5.3": OFF,
         "claude-opus-5.5": {"temperature": None}}  # its endpoint rejects the temperature parameter
# USD per 1M tokens (input, output); list prices used by the sibling sessions on 2026-11-03
PRICES = {"glm-air": (0.20, 1.10), "ds-flash": (0.30, 1.20), "ds-pro": (1.32, 3.96), "kimi-k2.6": (0.95, 4.00),
          "gpt-6-sol": (0.0, 0.0), "glm-5.3": (0.0, 0.0), "claude-opus-5.5": (0.0, 0.0)}  # served through the organisation's internal gateway; no list price recorded
DAILY_CAP = float(os.environ.get("DAILY_CAP", 5.0))
_lock = threading.Lock()
_spent = {}


def cost(model, usage):
    pi, po = PRICES[model]
    return (usage.get("prompt_tokens", 0) * pi + usage.get("completion_tokens", 0) * po) / 1e6


if os.path.exists(LOG):
    _today = datetime.date.today().isoformat()
    for _l in open(LOG):
        _d = json.loads(_l)
        if _d.get("day") == _today:
            _spent[_d["m"]] = _spent.get(_d["m"], 0) + _d.get("usd", 0)


def chat(model, messages, tools=None, temperature=0.0, max_tokens=1200, rep=0, retries=8):
    """Returns dict(message, usage, usd, latency, cached). `message` is the assistant message (content, tool_calls)."""
    prov, name = MODELS[model]
    kw = {k: v for k, v in FIXED.get(model, {}).items() if k != "temperature"}
    temperature = FIXED.get(model, {}).get("temperature", temperature)
    body = {"model": name, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, **kw}
    if temperature is None:
        del body["temperature"]
    if tools:
        body["tools"] = tools
    key = hashlib.sha256(json.dumps([prov, body, rep], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    path = os.path.join(CACHE_DIR, key[:2], key + ".json")
    if os.path.exists(path):
        return {**json.load(open(path)), "cached": True}
    if _spent.get(model, 0) > DAILY_CAP:
        raise RuntimeError(f"daily cap reached for {model}")
    if prov == "llmhub":  # OpenAI-compatible gateway; endpoint and key only from the environment, never stored
        cfg, err = {"base_url": os.environ["LLMHUB_BASE_URL"], "api_key": os.environ["LLMHUB_API_KEY"]}, None
    else:
        cfg, err = KEYS[prov], None
    for i in range(retries):
        try:
            t0 = time.time()
            r = requests.post(cfg["base_url"].rstrip("/") + "/chat/completions",
                              headers={"Authorization": "Bearer " + cfg["api_key"]}, json=body, timeout=180)
            lat = time.time() - t0
            if r.status_code != 200:
                err = f"{r.status_code} {r.text[:300]}"
                if r.status_code == 400:
                    raise RuntimeError(err)
                time.sleep(min(60, 2 ** i) + (5 if r.status_code == 429 else 0))
                continue
            d = r.json()
            m = d["choices"][0]["message"]
            msg = {"role": "assistant", "content": m.get("content") or ""}
            if m.get("tool_calls"):
                msg["tool_calls"] = [{"id": t["id"], "type": "function",
                                      "function": {"name": t["function"]["name"],
                                                   "arguments": t["function"].get("arguments") or "{}"}}
                                     for t in m["tool_calls"]]
            u = d.get("usage") or {}
            out = {"message": msg, "usage": u, "usd": cost(model, u), "latency": lat,
                   "finish": d["choices"][0].get("finish_reason")}
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with _lock:
                json.dump(out, open(path, "w"), ensure_ascii=False)
                _spent[model] = _spent.get(model, 0) + out["usd"]
                with open(LOG, "a") as f:
                    f.write(json.dumps({"day": datetime.date.today().isoformat(), "t": time.time(), "m": model,
                                        "usd": out["usd"], "lat": lat,
                                        "pt": u.get("prompt_tokens", 0), "ct": u.get("completion_tokens", 0)}) + "\n")
            return {**out, "cached": False}
        except requests.RequestException as e:
            err = repr(e)
            time.sleep(min(60, 2 ** i))
    raise RuntimeError(err)


def spent_today():
    return dict(_spent)
