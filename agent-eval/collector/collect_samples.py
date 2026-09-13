# -*- coding: utf-8 -*-
"""采集脚本（教程第 13 篇 4.4 节）：流式调 Dify Agent，拼接交付、采 usage 与干净轨迹。

用法：
    export DIFY_API_KEY=app-你的密钥
    python collect_samples.py [--repeat] [--dry-run]

可选环境变量：
    DIFY_BASE_URL  Dify 地址，默认 http://127.0.0.1
    AGENT_REPEAT   P0 任务重复次数，默认 3（--repeat 开关控制是否启用）

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

# 兼容两种运行方式：pytest/conftest 路径 + 直接 python 运行路径
try:
    from collector.mock_responses import MOCK_RESPONSES   # 通过 pytest 运行（conftest.py 加了根目录）
except ImportError:
    from mock_responses import MOCK_RESPONSES             # 直接 python collect_samples.py 运行

BASE_URL = os.getenv("DIFY_BASE_URL", "http://127.0.0.1").rstrip("/")
API_URL = f"{BASE_URL}/v1/chat-messages"
DATASET = Path(__file__).resolve().parent.parent / "dataset" / "dataset.csv"
OUT = Path(__file__).resolve().parent / "samples.json"
TIMEOUT = 600        # Agent 任务分钟级
P0_REPEAT = int(os.getenv("AGENT_REPEAT", "3"))
DRY_RUN_IDS = ("AG-0003", "AG-0201", "AG-0301")


def _heartbeat(start: float, step: int, tool: str, q_len: int):
    """流式期间的心跳：每收到一个事件就刷新一行，让用户知道 Agent 还在干活"""
    elapsed = round(time.time() - start, 0)
    tool_info = f"工具:{tool}" if tool else "思考中"
    print(f"\r    ⏱ {elapsed:>3.0f}s │ 轨迹第 {step} 步 │ {tool_info} │ 事件 {q_len} 条    ",
          file=sys.stderr, end="", flush=True)


def ask_dify_stream(question: str, show_progress: bool = True) -> dict:
    """流式调 Agent：拼接 agent_message 增量为完整交付；每步只留最后一条 agent_thought（干净轨迹）。

    show_progress=True 时，往 stderr 写实时心跳（pytest 不吞 stderr，终端能看到）。
    """
    payload = {
        "inputs": {},
        "query": question,
        "response_mode": "streaming",    # Agent 应用只支持流式（教程 1.3 节实测 400）
        "conversation_id": "",
        "user": "eval-runner",
    }
    headers = {
        "Authorization": "Bearer " + os.environ["DIFY_API_KEY"],
        "Content-Type": "application/json",
    }
    answer, final_answer = "", ""
    usage, retriever = {}, []
    last_thought = {}    # position -> 该步最后一条 thought（干净轨迹）
    event_count = 0
    _last_beat = 0
    start = time.time()

    with requests.post(API_URL, headers=headers, json=payload,
                       stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data:"):
                continue
            try:
                d = json.loads(raw[5:].strip())
            except json.JSONDecodeError:
                continue
            event_count += 1
            ev = d.get("event")

            # 心跳：每收到 500 个事件或过了 5 秒刷一次，让用户看到进度
            if show_progress and (event_count % 500 == 0 or time.time() - _last_beat > 5):
                _heartbeat(start, len(last_thought), d.get("tool", ""), event_count)
                _last_beat = time.time()

            if ev == "agent_message":
                answer += d.get("answer", "")
            elif ev == "message":
                final_answer = d.get("answer", "")
            elif ev == "message_end":
                meta = d.get("metadata") or {}
                usage = meta.get("usage") or {}
                retriever = meta.get("retriever_resources") or []
            elif ev == "agent_thought":
                last_thought[d.get("position")] = {
                    "tool": d.get("tool"),
                    "tool_input": (d.get("tool_input") or "")[:200],
                    "observation": (d.get("observation") or "")[:200],
                }

    trajectory = [last_thought[p] for p in sorted(last_thought)]
    latency = round(time.time() - start, 1)
    if show_progress:
        print(f"\r    ✓ 完成：{latency}s / {len(trajectory)} 步 / {usage.get('total_tokens', '?')} tok"
              + " " * 30, file=sys.stderr, flush=True)
    return {
        "response": final_answer or answer,
        "latency": latency,
        "tokens": usage.get("total_tokens", 0),
        "price": usage.get("total_price"),
        "retriever": retriever,
        "trajectory": trajectory,
    }


def trajectory_stats(trajectory: list) -> dict:
    """简版轨迹指标（教程 2.2 节）：步骤数、工具调用分布、知识库白查标记"""
    return {
        "steps": len(trajectory),
        "tool_calls": sorted({t["tool"] for t in trajectory if t["tool"]}),
        "kb_empty": any(t["tool"] == "knowledge_base_search"
                         and "No relevant" in t["observation"]
                         for t in trajectory),
    }


def run_id(tid: str, i: int) -> str:
    return tid if i == 1 else f"{tid}#{i}"


def main():
    if "DIFY_API_KEY" not in os.environ:
        sys.exit("请先 export DIFY_API_KEY=app-你的密钥")

    with open(DATASET, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if "--dry-run" in sys.argv:
        rows = [r for r in rows if r["编号"] in DRY_RUN_IDS]
        print(f"[dry-run] 只跑 {len(rows)} 条冒烟")

    MOCK = "--mock" in sys.argv
    if MOCK:
        print("[mock] 使用 Mock 模式：不调 Agent，读预置响应，零 token 消耗")

    use_repeat = "--repeat" in sys.argv
    samples = []
    for r in rows:
        repeats = P0_REPEAT if (use_repeat and r["优先级"] == "P0") else 1
        for i in range(1, repeats + 1):
            rid = run_id(r["编号"], i)
            print(f"[{rid}] {r['任务输入'][:50]}…")
            try:
                if MOCK:
                    mock = MOCK_RESPONSES.get(rid) or MOCK_RESPONSES.get(r["编号"], {})
                    out = {"response": mock.get("response", ""),
                           "latency": mock.get("latency", 0),
                           "tokens": mock.get("tokens", 0),
                           "price": mock.get("price", 0),
                           "trajectory": mock.get("trajectory", []),
                           "retriever": mock.get("retriever", [])}
                else:
                    out = ask_dify_stream(r["任务输入"])
            except Exception as e:
                print(f"    采集失败：{e}")
                continue
            samples.append({
                "id": rid,
                "layer": r["层级"],
                "scene": r["场景"],
                "user_input": r["任务输入"],
                "response": out["response"],
                "reference": r.get("判定标准", ""),
                "latency": out["latency"],
                "tokens": out["tokens"],
                "price": out["price"],
                "retriever": out["retriever"],
                "trajectory": out["trajectory"],
                "trajectory_stats": trajectory_stats(out["trajectory"]),
            })
            stats = out["trajectory"] and trajectory_stats(out["trajectory"])
            print(f"    时延 {out['latency']}s | token {out['tokens']} | "
                  f"价格 {out['price']} | 轨迹 {len(out['trajectory'])} 步")
            if not MOCK:
                time.sleep(2)    # Agent 任务重，给 worker 留口气（Mock 模式不用等）

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    print(f"\n采集完成 {len(samples)} 条，已写入 {OUT}")


if __name__ == "__main__":
    main()
