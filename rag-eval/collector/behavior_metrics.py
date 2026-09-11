# -*- coding: utf-8 -*-
"""行为类指标（教程第 12 篇 4.5 节）：P95 / 最大 / 平均完整时延、token 消耗。

数据来源是采集脚本顺手记下的 latency 和 tokens，无需单独跑。
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
    """最近邻法取分位数（与 numpy 默认线性插值略有差异，量小可忽略）。"""
    if not sorted_vals:
        return None
    idx = max(0, math.ceil(p / 100 * len(sorted_vals)) - 1)
    return sorted_vals[idx]


def main():
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))

    latencies = sorted(s["latency"] for s in samples)
    tokens = [s["tokens"] for s in samples]

    result = {
        "sample_file": str(SAMPLES),
        "queries": len(samples),
        "latency_avg_s": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "latency_p95_s": percentile(latencies, 95),
        "latency_max_s": max(latencies) if latencies else None,
        "tokens_avg": round(sum(tokens) / len(tokens)) if tokens else None,
        "tokens_total": sum(tokens),
    }

    print(f"共 {result['queries']} 条查询")
    print(f"完整时延：平均 {result['latency_avg_s']}s | P95 {result['latency_p95_s']}s | 最大 {result['latency_max_s']}s")
    print(f"token 消耗：单条平均 {result['tokens_avg']} | 整轮合计 {result['tokens_total']}")
    print("提示：本地 Dify + 云端模型的 blocking 调用，首轮常有 10 秒以上的冷启动，多轮取数后再看 P95 更有代表性")

    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"明细已写入 {REPORT}")


if __name__ == "__main__":
    main()
