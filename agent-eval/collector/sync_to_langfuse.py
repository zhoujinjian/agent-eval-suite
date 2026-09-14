# -*- coding: utf-8 -*-
"""把 Agent 评测数据（samples.json）同步到 Langfuse：轨迹变 span、交付变 output、评测变 score

教程第 14 篇 3.3 节。读取 13 篇采集脚本的 samples.json，
把每条任务的轨迹、交付、评测分数同步到 Langfuse 平台。

用法：
    # 第一步：先跑采集（Mock 或真实模式）
    cd agent-eval/collector
    python collect_samples.py --mock

    # 第二步：同步到 Langfuse
    python sync_to_langfuse.py samples.json

前置条件：
    1. Langfuse 已部署并启动（11 篇 2.2 节）
    2. 环境变量已配好（11 篇 2.3 节）：
       export LANGFUSE_PUBLIC_KEY=pk-lf-xxxx
       export LANGFUSE_SECRET_KEY=sk-lf-xxxx
       export LANGFUSE_BASE_URL=http://127.0.0.1:3000

验证：
    同步完成后打开 Langfuse → Traces
    能看到 agent_task_xxx 开头的 trace，每条包含：
    - input：任务输入
    - span 列表：Agent 轨迹的每一步（工具名、入参、执行结果）
    - output：最终交付
    - metadata：耗时、token、成本
    - score：评测分数 task_completion（读 report/eval-scores.json，
      由 deepeval/eval_tests.py 跑完评测后落盘，含裁判分数与理由）

依赖：pip install langfuse
"""
import json
import os
import sys
from pathlib import Path


def check_env():
    """检查 Langfuse 环境变量"""
    required = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"❌ 缺少环境变量: {', '.join(missing)}")
        print("   参照教程 11 篇 2.3 节配置 Langfuse 的三个环境变量")
        sys.exit(1)


def sync_sample(langfuse, sample: dict, sc: dict = None) -> str:
    """把一条样本同步到 Langfuse，返回 trace ID

    sc 是该任务的评测结果（来自 report/eval-scores.json，跑过 deepeval 才有）：
    {"passed": bool, "score": 0~1 或 None, "reason": "..."}
    """
    # 创建根观测（Langfuse SDK v3+ 没有 trace() 方法，根观测就是一条 trace）
    root = langfuse.start_observation(
        name=f"agent_task_{sample['id']}",
        input={"question": sample.get("user_input", "")[:1000]},
        metadata={
            "task_id": sample.get("id", ""),
            "layer": sample.get("layer", ""),
            "scene": sample.get("scene", ""),
            "latency_s": sample.get("latency", 0),
            "tokens": sample.get("tokens", 0),
            "price": sample.get("price", ""),
        },
    )

    # 把轨迹的每一步变成根观测下的子观测（span）
    for i, step in enumerate(sample.get("trajectory", [])):
        tool = step.get("tool") or "thinking"
        child = root.start_observation(
            name=f"step_{i+1}_{tool}",
            input=str(step.get("tool_input", ""))[:500],
            output=str(step.get("observation", ""))[:500],
            metadata={"tool": tool},
        )
        child.end()

    # 最终交付作为 trace 的 output
    root.update(output=str(sample.get("response", ""))[:2000])

    # 挂评测分数：优先用 DeepEval 落盘的分数（report/eval-scores.json），
    # 兼容手工补在样本里的 eval_score 字段
    if sc:
        value = sc.get("score")
        if value is None:  # 前两层就挂掉的没有裁判分，用 0/1 表示通过与否
            value = 1 if sc.get("passed") else 0
        root.score_trace(
            name="task_completion",
            value=value,
            comment=str(sc.get("reason", ""))[:500],
            data_type="NUMERIC",
        )
    elif sample.get("eval_score") is not None:
        root.score_trace(
            name="task_completion",
            value=sample["eval_score"],
            comment=str(sample.get("eval_reason", ""))[:500],
            data_type="NUMERIC",
        )

    root.end()
    return root.trace_id


def main():
    # 读命令行参数
    samples_file = sys.argv[1] if len(sys.argv) > 1 else "samples.json"
    path = Path(samples_file)

    if not path.exists():
        print(f"❌ 文件不存在: {path}")
        print("   先跑采集: python collect_samples.py --mock")
        sys.exit(1)

    check_env()
    from langfuse import Langfuse
    langfuse = Langfuse()

    # 读 samples.json
    samples = json.loads(path.read_text(encoding="utf-8"))
    if not samples:
        print("❌ samples.json 是空的")
        sys.exit(1)

    # 读评测分数：跑过 deepeval 才有（report/eval-scores.json），没有就只同步轨迹
    scores_path = Path(__file__).resolve().parent.parent / "report" / "eval-scores.json"
    scores = json.loads(scores_path.read_text(encoding="utf-8")) if scores_path.exists() else {}
    if scores:
        print(f"  已加载 {len(scores)} 条评测分数（report/eval-scores.json）")
    else:
        print("  ⚠ 未找到 report/eval-scores.json，本次只同步轨迹不带分数")
        print("    想带分数：先跑一轮 EVAL_MOCK=1 deepeval test run deepeval/eval_tests.py")

    # 逐条同步
    print(f"开始同步 {len(samples)} 条到 Langfuse…")
    trace_ids = []
    for sample in samples:
        try:
            tid = sync_sample(langfuse, sample, scores.get(sample.get("id")))
            trace_ids.append(tid)
            print(f"  ✓ {sample['id']} → trace: {tid[:16]}…")
        except Exception as e:
            print(f"  ✗ {sample['id']} 同步失败: {e}")

    # SDK 是异步批量上报，退出前必须 flush，否则进程退出数据就丢了
    langfuse.flush()

    print(f"\n{'='*50}")
    print(f"✓ 同步完成: {len(trace_ids)}/{len(samples)} 条成功")
    host = os.getenv("LANGFUSE_BASE_URL", "http://127.0.0.1:3000")
    print(f"  打开 {host} → Traces 查看")
    print(f"  每个 trace 包含: input → span 列表（轨迹每一步）→ output → metadata")


if __name__ == "__main__":
    main()
