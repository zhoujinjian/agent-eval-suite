#!/usr/bin/env bash
# 一键串联：断言评测 → 采集 → 检索层指标 → 行为类指标 → RAGAS
# 用法：./run_all.sh
set -uo pipefail
cd "$(dirname "$0")"

if [ -z "${DIFY_API_KEY:-}" ]; then
  echo "❌ 请先 export DIFY_API_KEY=app-你的密钥"; exit 1
fi

# RAGAS 用哪个 Python：本目录自建 ragas-env > 上两级的 ragas-env（09 篇教程环境）> 系统 python3
RAGAS_PY=""
[ -x "ragas-env/bin/python" ] && RAGAS_PY="ragas-env/bin/python"
[ -z "$RAGAS_PY" ] && [ -x "../../ragas-env/bin/python" ] && RAGAS_PY="../../ragas-env/bin/python"
[ -z "$RAGAS_PY" ] && RAGAS_PY="$(command -v python3)"

echo "===== [1/5] Promptfoo 断言评测（20 条，约 5~8 分钟）====="
npx -y promptfoo@latest eval -c promptfoo/promptfooconfig.yaml \
  || echo "⚠️ 整体通过率低于门禁 0.9（详见报告），继续采集数据"

echo
echo "===== [2/5] 采集回答/检索/时延/token ====="
"$RAGAS_PY" collector/collect_samples.py || { echo "❌ 采集失败，后续步骤中止"; exit 1; }

echo
echo "===== [3/5] 检索层指标（命中率@5 / MRR / 误召回）====="
"$RAGAS_PY" collector/retrieval_metrics.py

echo
echo "===== [4/5] 行为类指标（P95 时延 / token）====="
"$RAGAS_PY" collector/behavior_metrics.py

echo
echo "===== [5/5] RAGAS 三指标 ====="
if [ -z "${ZAI_API_KEY:-}" ]; then
  echo "⚠️ 未设置 ZAI_API_KEY，跳过 RAGAS。设置后手动运行："
  echo "   $RAGAS_PY ragas/rag_eval.py"
else
  "$RAGAS_PY" ragas/rag_eval.py || echo "⚠️ RAGAS 失败，检查是否在 ragas 虚拟环境（README 环境准备）"
fi

echo
echo "===== 完成 ====="
echo "产出：collector/samples.json | report/retrieval-metrics.json | report/behavior-metrics.json"
echo "下一步：打开 report/eval-report-v0.1.md，按文末填数索引填报告"
