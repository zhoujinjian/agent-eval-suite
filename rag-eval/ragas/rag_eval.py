# -*- coding: utf-8 -*-
"""生成层/检索层语义指标（教程第 12 篇 4.4 节）：RAGAS 三把尺子。

指标：
- Faithfulness（忠实度，生成层）：回答是否严格基于检索内容
- LLMContextRecall（上下文召回，检索层）：该覆盖的要点漏没漏
- LLMContextPrecisionWithReference（上下文精确率，检索层）：检回的垃圾多不多

样本口径：只喂「有参考答案且检索非空」的题（拒答题、无参考答案的题由断言层负责）。

用法（在 ragas 虚拟环境里，09 篇的环境划分原则）：
    export ZAI_API_KEY=你的智谱Key
    python rag_eval.py              # 全量
    RAGAS_SMOKE=1 python rag_eval.py  # 只取前 3 条，先验证配置再放全量（省 token）

产出：终端打印总分 + report/ragas-scores.csv（逐条分数）
"""
import json
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="Importing .* from 'ragas.metrics' is deprecated")

from openai import OpenAI
from ragas import evaluate, EvaluationDataset
from ragas.llms import llm_factory
from ragas.metrics import Faithfulness, LLMContextRecall, LLMContextPrecisionWithReference

SAMPLES = Path(__file__).resolve().parent.parent / "collector" / "samples.json"
REPORT_DIR = Path(__file__).resolve().parent.parent / "report"
SCORES_CSV = REPORT_DIR / "ragas-scores.csv"


def main():
    if "ZAI_API_KEY" not in os.environ:
        sys.exit("请先 export ZAI_API_KEY=你的智谱Key（09 篇教程申请的同一把）")

    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))

    rows = [
        {
            "user_input": s["user_input"],
            "response": s["response"],
            "retrieved_contexts": [c["content"] for c in s["contexts"]],
            "reference": s["reference"],
        }
        for s in samples
        if s.get("reference") and s.get("contexts")   # 有参考答案且检索非空才进
    ]

    if not rows:
        sys.exit("没有可评测的样本（需要有参考答案且检索非空的条目），先跑采集脚本")

    if os.getenv("RAGAS_SMOKE"):
        rows = rows[:3]
        print(f"[smoke] 只取前 {len(rows)} 条验证配置")

    # 裁判：智谱 GLM-5.3，09 篇实测参数原样带（防思考链截断 + 低推理力度）
    zhipu = OpenAI(
        api_key=os.environ["ZAI_API_KEY"],
        base_url="https://open.bigmodel.cn/api/paas/v4/",
    )
    judge = llm_factory("glm-5.3", client=zhipu,
                        max_tokens=8192, reasoning_effort="low")

    print(f"开始评测 {len(rows)} 条样本，3 个指标全走裁判，耐心等…")
    result = evaluate(
        dataset=EvaluationDataset.from_list(rows),
        metrics=[Faithfulness(), LLMContextRecall(), LLMContextPrecisionWithReference()],
        llm=judge,
    )
    print("\n===== 总分 =====")
    print(result)

    REPORT_DIR.mkdir(exist_ok=True)
    df = result.to_pandas()
    df.to_csv(SCORES_CSV, index=False)

    print(f"\n逐条分数已写入 {SCORES_CSV}")
    print("各指标均值（0~1，越高越好）：")
    for col, val in df.mean(numeric_only=True).items():
        if val == val:   # 过滤 nan
            print(f"  {col}: {val:.3f}")


if __name__ == "__main__":
    main()
