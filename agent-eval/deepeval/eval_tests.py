# -*- coding: utf-8 -*-
"""DeepEval 主程序（教程第 13 篇 4.2 节）：三层判定组装。

运行：
    EVAL_MOCK=1 deepeval test run eval_tests.py   # Mock 模式（教程推荐，≈¥0.2 / 2分钟）
    deepeval test run eval_tests.py -k AG-0003    # 真实跑单条（冒烟体验，≈¥8.5 / 5分钟）
    deepeval test run eval_tests.py               # 全量真实（生产用，≈¥85 / 50~100分钟）

前置：
    export DIFY_API_KEY=app-你的密钥    # 被测 Agent
    export ZAI_API_KEY=你的智谱Key      # TaskCompletion 裁判
"""
import csv
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import TaskCompletionMetric

# collector / verifier 的导入靠项目根目录的 conftest.py（pytest 自动加路径）
from collector.collect_samples import ask_dify_stream
from collector.mock_responses import MOCK_RESPONSES
from verifier.verify_code import verify_one

# Mock 模式：不调 Agent，用预置响应（教程阶段省 token 省时间，详见 4.2 节）
MOCK_MODE = os.environ.get("EVAL_MOCK", "") == "1"

DATASET = Path(__file__).resolve().parent.parent / "dataset" / "dataset.csv"
TASKS = list(csv.DictReader(open(DATASET, encoding="utf-8-sig")))

# 三块结构正则（容错：## 代码 / ## 1、代码 / ## 1. 代码 都算命中——实测模型会加编号）
BLOCKS = {
    "代码": r"##\s*\d*[、.]?\s*代码",
    "依赖": r"##\s*\d*[、.]?\s*依赖",
    "使用说明": r"##\s*\d*[、.]?\s*使用说明",
}

# ---- 进度显示：往 stderr 写（pytest 不捕获 stderr，终端实时可见）----
_progress = {"current": 0, "total": len(TASKS), "pass": 0, "fail": 0}

def progress(msg: str):
    """打印进度信息到 stderr，带时间戳和进度条"""
    ts = time.strftime("%H:%M:%S")
    cur = _progress["current"]
    total = _progress["total"]
    bar_len = 20
    filled = int(bar_len * cur / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    pct = cur * 100 // total
    print(f"\r  [{ts}] {bar} {pct}% ({cur}/{total}) │ ✓{_progress['pass']} ✗{_progress['fail']} │ {msg}    ",
          file=sys.stderr, end="", flush=True)


@pytest.mark.parametrize("task", TASKS, ids=[t["编号"] for t in TASKS])
def test_agent_task(task):
    tid = task["编号"]
    progress(f"▶ {tid} {'[Mock]' if MOCK_MODE else ''}调用 Agent 中…")

    t0 = time.time()

    # ---- 取交付：Mock 模式读预置响应，真实模式调 Agent ----
    if MOCK_MODE:
        mock = MOCK_RESPONSES.get(tid, {})
        sample = {"response": mock.get("response", ""),
                  "latency": mock.get("latency", 0),
                  "tokens": mock.get("tokens", 0),
                  "trajectory": mock.get("trajectory", [])}
    else:
        sample = ask_dify_stream(task["任务输入"])
    delivery = sample["response"]

    elapsed = round(time.time() - t0, 0)
    steps = len(sample.get("trajectory", []))
    tokens = sample.get("tokens", 0)
    progress(f"▶ {tid} Agent 返回（{elapsed}s / {steps}步 / {tokens} tok），判定中…")

    missing = [b for b, pat in BLOCKS.items() if not re.search(pat, delivery)]
    assert not missing, f"交付缺了 {missing} 块（检查项 A2）"

    # ---- 第二层：执行验证（「不执行」的危险/对抗任务跳过）----
    if task["验证级"] != "不执行":
        progress(f"▶ {tid} 执行验证中…（L{task['验证级']}）")
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
    progress(f"▶ {tid} 语义评审中…（裁判 glm-5.3）")
    test_case = LLMTestCase(
        input=task["任务输入"],
        actual_output=delivery,
        expected_output=task["判定标准"],
    )
    metric = TaskCompletionMetric(threshold=0.8, model="glm-5.3")
    assert_test(test_case, [metric])

    # ---- 收尾：更新进度 ----
    _progress["current"] += 1
    _progress["pass"] += 1
    progress(f"✓ {tid} 三层全过")

    # 完成时换行，避免进度条和下一条测试的输出挤在一行
    if _progress["current"] >= _progress["total"]:
        print(file=sys.stderr)  # 最终换行
