# -*- coding: utf-8 -*-
"""DeepEval 主程序（教程第 13 篇 4.2 节）：三层判定组装。

运行：deepeval test run eval_tests.py             # 全部 10 个任务
      deepeval test run eval_tests.py -k AG-0003  # 只跑单条（冒烟、复判）

前置：
    export DIFY_API_KEY=app-你的密钥    # 被测 Agent
    export ZAI_API_KEY=你的智谱Key      # TaskCompletion 裁判
"""
import csv
import re
import shutil
import sys
import tempfile
from pathlib import Path

# 把项目根目录（agent-eval/）加入 sys.path，让兄弟目录的模块可导入
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import TaskCompletionMetric

from collector.collect_samples import ask_dify_stream
from verifier.verify_code import verify_one

DATASET = Path(__file__).resolve().parent.parent / "dataset" / "dataset.csv"
TASKS = list(csv.DictReader(open(DATASET, encoding="utf-8-sig")))

# 三块结构正则（容错：## 代码 / ## 1、代码 / ## 1. 代码 都算命中——实测模型会加编号）
BLOCKS = {
    "代码": r"##\s*\d*[、.]?\s*代码",
    "依赖": r"##\s*\d*[、.]?\s*依赖",
    "使用说明": r"##\s*\d*[、.]?\s*使用说明",
}


@pytest.mark.parametrize("task", TASKS, ids=[t["编号"] for t in TASKS])
def test_agent_task(task):
    # ---- 第一层：结构断言（pytest 原生 assert，零成本）----
    sample = ask_dify_stream(task["任务输入"])
    delivery = sample["response"]
    missing = [b for b, pat in BLOCKS.items() if not re.search(pat, delivery)]
    assert not missing, f"交付缺了 {missing} 块（检查项 A2）"

    # ---- 第二层：执行验证（「不执行」的危险/对抗任务跳过）----
    if task["验证级"] != "不执行":
        workdir = Path(tempfile.mkdtemp(prefix="t_"))
        try:
            result = verify_one(sample, task, workdir)
            assert result["pass"], f"执行验证未过：{result.get('reason')}"
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    # ---- 第二层半：能力调用的轨迹断言（仅带「期望调用」的任务，3.1 节）----
    if task.get("期望调用"):
        tools = {step["tool"] for step in sample["trajectory"] if step["tool"]}
        assert task["期望调用"] in tools, \
            f"该调的 {task['期望调用']} 没调，轨迹里只有：{tools or '无'}"

    # ---- 第三层：语义评审（TaskCompletion = LLM 裁判，判「任务按标准算不算完成」）----
    test_case = LLMTestCase(
        input=task["任务输入"],
        actual_output=delivery,
        expected_output=task["判定标准"],
    )
    metric = TaskCompletionMetric(threshold=0.8, model="glm-5.3")
    assert_test(test_case, [metric])
