# -*- coding: utf-8 -*-
"""检索层指标（教程第 12 篇 4.3 节）：命中率@5、MRR、拒答误召回。

统计口径：
- 有据可查的题（高频主流程 + 边界条件）算命中率@5 和 MRR
- 应拒答（库外题）不进上述统计，单看「误召回」：不该捞回内容却捞回了
- 对抗安全题检索层不统计——像「确认 90% 通过率」这类指着库内内容的对抗题，
  检回相关文档恰恰是纠正错误前提的必要条件，算误召回会冤枉它；对抗行为由断言层判定
- 参考片段匹配规则（04 篇 3.7）：参考文档名匹配 + 片段开头前 20 字匹配；
  「参考片段开头」留空的题，按文档名匹配兜底

用法：python retrieval_metrics.py [samples.json 路径]   # 默认读本目录 samples.json
产出：终端打印 + report/retrieval-metrics.json
"""
import json
import sys
from pathlib import Path

SAMPLES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "samples.json"
REPORT = Path(__file__).resolve().parent.parent / "report" / "retrieval-metrics.json"

IN_LIB_LAYERS = ("高频主流程", "边界条件")     # 有据可查，进命中率/MRR
REFUSAL_LAYER = "应拒答"                       # 库外题，单看误召回
ADVERSARIAL_LAYER = "对抗安全"                 # 检索层不统计，断言层判定
SNIPPET_LEN = 20


def find_rank(sample: dict):
    """参考片段在检回列表里的排名（position 字段），没找到返回 None。"""
    for c in sample.get("contexts", []):
        if sample.get("ref_doc") and sample["ref_doc"] in c.get("document", ""):
            snippet = (sample.get("ref_snippet") or "").strip()
            # 片段开头留空 → 按文档名匹配即可（兜底口径）
            if not snippet or snippet[:SNIPPET_LEN] in c.get("content", ""):
                return c.get("position")
    return None


def main():
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))

    hits, reciprocal_ranks, missed = [], [], []
    wrong_recall = []
    n_refusal = 0

    for s in samples:
        layer = s.get("layer", "")
        if layer == ADVERSARIAL_LAYER:
            continue
        if layer == REFUSAL_LAYER:
            n_refusal += 1
            if s.get("contexts"):
                wrong_recall.append({
                    "id": s["id"],
                    "retrieved_docs": [c["document"] for c in s["contexts"]],
                    "top_score": s["contexts"][0].get("score"),
                })
            continue

        rank = find_rank(s)
        if rank is None:
            hits.append(0)
            reciprocal_ranks.append(0.0)
            missed.append(s["id"])
        else:
            hits.append(1)
            reciprocal_ranks.append(1.0 / rank)

    n = len(hits)
    result = {
        "sample_file": str(SAMPLES),
        "in_lib_total": n,
        "hit_at_5": round(sum(hits) / n, 4) if n else None,
        "mrr": round(sum(reciprocal_ranks) / n, 4) if n else None,
        "missed_ids": missed,
        "refusal_total": n_refusal,
        "wrong_recall_total": len(wrong_recall),
        "wrong_recall_detail": wrong_recall,
    }

    print(f"有据题 {n} 条：命中率@5 = {result['hit_at_5']:.0%}，MRR = {result['mrr']:.3f}" if n else "没有可统计的有据题")
    if missed:
        print(f"未召回（前 5 没找到参考片段）：{', '.join(missed)}")
    print(f"拒答/对抗题 {n_refusal} 条：误召回 {len(wrong_recall)} 条")
    for w in wrong_recall:
        print(f"  [误召回] {w['id']} 捞回了：{w['retrieved_docs']}（最高分 {w['top_score']:.2f}）")

    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"明细已写入 {REPORT}")


if __name__ == "__main__":
    main()
