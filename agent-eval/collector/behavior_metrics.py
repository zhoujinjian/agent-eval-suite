# -*- coding: utf-8 -*-
"""行为类指标（教程第 13 篇 4.5 节）：任务耗时 P95、token 与成本。

用法：python behavior_metrics.py [samples.json 路径]
产出：终端打印 + report/behavior-metrics.json
"""
import json
import math
import sys
from pathlib import Path

SAMPLES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "samples.json"
REPORT = Path(__file__).resolve().parent.parent / "report" / "behavior-metrics.json"


def percentile(sorted_vals, p):
    if not sorted_vals:
        return None
    idx = max(0, math.ceil(p / 100 * len(sorted_vals)) - 1)
    return sorted_vals[idx]


def main():
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    latencies = sorted(s["latency"] for s in samples)
    tokens = [s["tokens"] for s in samples]
    prices = [s["price"] for s in samples if s.get("price")]

    result = {
        "sample_file": str(SAMPLES),
        "tasks": len(samples),
        "latency_avg_s": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "latency_p95_s": percentile(latencies, 95),
        "latency_max_s": max(latencies) if latencies else None,
        "tokens_avg": round(sum(tokens) / len(tokens)) if tokens else None,
        "tokens_total": sum(tokens),
        "price_total": round(sum(prices), 2) if prices else None,
    }

    print(f"共 {result['tasks']} 条任务")
    print(f"任务耗时：平均 {result['latency_avg_s']}s | P95 {result['latency_p95_s']}s | 最大 {result['latency_max_s']}s")
    print(f"token 消耗：单条平均 {result['tokens_avg']} | 整轮合计 {result['tokens_total']}")
    if result["price_total"]:
        print(f"本轮总成本：¥{result['price_total']}（usage 自带 total_price，不用乘单价表）")

    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"明细已写入 {REPORT}")


if __name__ == "__main__":
    main()
