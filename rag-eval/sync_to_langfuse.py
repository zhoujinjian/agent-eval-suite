# -*- coding: utf-8 -*-
"""把 Promptfoo 评测结果同步到 Langfuse（教程第 14 篇 3.2 节）

用法：
    # 第一步：先跑 Promptfoo 评测并导出 JSON
    cd rag-eval/promptfoo
    npx promptfoo@latest eval -c promptfooconfig.yaml -o ../results.json

    # 第二步：同步到 Langfuse
    cd ..
    python sync_to_langfuse.py results.json

前置条件：
    1. Langfuse 已部署并启动（11 篇 2.2 节）
    2. 环境变量已配好（11 篇 2.3 节）：
       export LANGFUSE_PUBLIC_KEY=pk-lf-xxxx
       export LANGFUSE_SECRET_KEY=sk-lf-xxxx
       export LANGFUSE_BASE_URL=http://127.0.0.1:3000

验证：
    同步完成后打开 Langfuse 界面 → Traces 页签
    能看到 rag_eval_xxx 开头的 trace，每条挂着 assertion_pass 分数

依赖：pip install langfuse
"""
import json
import sys
from pathlib import Path


def main():
    # 读命令行参数指定的 JSON 文件
    if len(sys.argv) < 2:
        print("用法: python sync_to_langfuse.py <results.json>")
        print("示例: python sync_to_langfuse.py results.json")
        sys.exit(1)

    results_file = Path(sys.argv[1])
    if not results_file.exists():
        print(f"❌ 文件不存在: {results_file}")
        print("   先跑 Promptfoo 并导出: npx promptfoo@latest eval -c promptfooconfig.yaml -o results.json")
        sys.exit(1)

    # 检查 Langfuse 环境变量
    import os
    required = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"❌ 缺少环境变量: {', '.join(missing)}")
        print("   参照教程 11 篇 2.3 节配置 Langfuse 的三个环境变量")
        sys.exit(1)

    from langfuse import Langfuse
    langfuse = Langfuse()

    # 读 Promptfoo 结果
    data = json.loads(results_file.read_text(encoding="utf-8"))
    results = data.get("results", [])

    if not results:
        print("❌ results.json 里没有评测结果")
        print("   先跑: npx promptfoo@latest eval -c promptfooconfig.yaml -o results.json")
        sys.exit(1)

    # 逐条同步
    synced = 0
    for r in results:
        question = str(r.get("vars", {}).get("question", "未知问题"))
        passed = r.get("success", False)
        response = str(r.get("response", ""))[:2000]  # 截断防超长

        # 创建 trace
        trace = langfuse.trace(
            name=f"rag_eval_{question[:30]}",
            input={"question": question},
            output={"response": response, "passed": passed},
        )

        # 挂分数
        trace.score(
            name="assertion_pass",
            value=1 if passed else 0,
            comment=f"Promptfoo 断言{'通过' if passed else '失败'}",
            data_type="NUMERIC",
        )
        synced += 1

    print(f"✓ 已同步 {synced} 条到 Langfuse")
    print(f"  打开 {os.getenv('LANGFUSE_BASE_URL', 'http://127.0.0.1:3000')} → Traces 查看")


if __name__ == "__main__":
    main()
