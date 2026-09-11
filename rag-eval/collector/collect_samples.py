# -*- coding: utf-8 -*-
"""采集脚本（教程第 12 篇 4.3 节）：调 Dify 应用 API，把 20 条题逐条问一遍，
采集回答、检索详情、时延、token，落成 samples.json。

用法：
    export DIFY_API_KEY=app-你的密钥
    python collect_samples.py            # 全量 20 条
    python collect_samples.py --dry-run  # 只跑 3 条冒烟（高频/拒答/对抗各 1）

可选环境变量：
    DIFY_BASE_URL  Dify 地址，默认 http://127.0.0.1（端口改过就 export，如 http://127.0.0.1:3000）

依赖：pip install requests
"""
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

BASE_URL = os.getenv("DIFY_BASE_URL", "http://127.0.0.1").rstrip("/")
API_URL = f"{BASE_URL}/v1/chat-messages"
DATASET = Path(__file__).resolve().parent.parent / "dataset" / "dataset.csv"
OUT = Path(__file__).resolve().parent / "samples.json"
MAX_RETRY = 3
DRY_RUN_IDS = ("EC-0001", "EC-0201", "EC-0301")

# 应用内是思考型模型，answer 里带 <think>...</think> 思考块，
# 断言和评测只针对可见回答，采集时剥掉（实测发现，必处理）
THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def strip_think(text: str) -> str:
    return THINK_RE.sub("", text or "").strip()


def ask_dify(question: str) -> dict:
    """调一次应用，带失败重试。返回回答（已剥 think）、时延、token、检回片段。"""
    headers = {
        "Authorization": "Bearer " + os.environ["DIFY_API_KEY"],
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": {},
        "query": question,
        "response_mode": "blocking",
        "conversation_id": "",   # 留空，每题开新会话，互不污染
        "user": "eval-runner",   # 固定 user，方便在 Dify 日志里区分评测流量
    }
    data = None
    for attempt in range(1, MAX_RETRY + 1):
        start = time.time()
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            if attempt == MAX_RETRY:
                raise
            wait = 2 * attempt
            print(f"    第 {attempt} 次请求失败（{e}），{wait}s 后重试")
            time.sleep(wait)
    latency = round(time.time() - start, 2)

    meta = data.get("metadata") or {}
    usage = meta.get("usage") or {}
    contexts = [
        {
            "document": c.get("document_name", ""),
            "position": c.get("position"),
            "score": c.get("score"),
            "content": c.get("content", ""),
        }
        for c in (meta.get("retriever_resources") or [])
    ]
    return {
        "response": strip_think(data.get("answer", "")),
        "latency": latency,
        "tokens": usage.get("total_tokens", 0),
        "contexts": contexts,
    }


def main():
    if "DIFY_API_KEY" not in os.environ:
        sys.exit("请先 export DIFY_API_KEY=app-你的密钥")

    # utf-8-sig 兼容 Excel 编辑后带的 BOM
    with open(DATASET, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if "--dry-run" in sys.argv:
        rows = [r for r in rows if r["编号"] in DRY_RUN_IDS]
        print(f"[dry-run] 只跑 {len(rows)} 条冒烟题")

    samples = []
    for i, r in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] {r['编号']}  {r['输入']}")
        try:
            out = ask_dify(r["输入"])
        except Exception as e:
            print(f"    请求失败（重试 {MAX_RETRY} 次后放弃）：{e}")
            continue
        samples.append({
            "id": r["编号"],
            "layer": r["层级"],
            "scene": r["场景"],
            "user_input": r["输入"],
            "response": out["response"],
            "reference": r.get("参考答案", ""),
            "ref_doc": r.get("参考文档", ""),
            "ref_snippet": r.get("参考片段开头", ""),
            "latency": out["latency"],
            "tokens": out["tokens"],
            "contexts": out["contexts"],
        })
        print(f"    时延 {out['latency']}s | token {out['tokens']} | 检回 {len(out['contexts'])} 段 | 回答 {len(out['response'])} 字")
        time.sleep(0.5)   # 轻微限速，给本地 worker 留口气

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)

    by_layer = {}
    for s in samples:
        by_layer[s["layer"]] = by_layer.get(s["layer"], 0) + 1
    print(f"\n采集完成 {len(samples)}/{len(rows)} 条，已写入 {OUT}")
    print("各层条数：" + "、".join(f"{k} {v}" for k, v in by_layer.items()))
    if len(samples) < len(rows):
        print("注意：有题采集失败，后续指标统计基于成功采集的部分")


if __name__ == "__main__":
    main()
