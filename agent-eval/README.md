# agent-eval · AI Coding Agent 评测项目

> `agent-eval-suite` 的第二个子项目，《AI 大模型测评体系》第 13 篇（Agent 项目评测实战）的配套可运行代码。被测对象是 Dify 系列第 7 讲搭起来的「AI Coding 提效工具生成 Agent」。

## 目录结构

```
agent-eval/
├── dataset/
│   ├── dataset.csv            # 10 个任务级用例（含期望调用/验证级/验证命令/验证断言列）
│   └── backlog.csv            # 候补池：首轮因成本裁掉的任务（含裁掉理由）
├── deepeval/
│   └── eval_tests.py          # DeepEval 主程序：三层判定组装（结构+执行+语义）
├── collector/
│   ├── collect_samples.py     # 流式调 Agent：拼接交付、采 usage 与干净轨迹
│   └── behavior_metrics.py    # 任务耗时 P95、token 与成本
├── verifier/
│   ├── verify_code.py         # 执行验证：提取代码 → 本地跑 → L1/L2/L3 断言
│   ├── verify_web.py          # Web 交付验证：Playwright 元素交互断言 + 截图
│   └── checks.py              # 独立核对函数（身份证校验位等）
├── ragas/                     # 空——检索质量不并入主链（README 写明原因）
└── report/
    └── eval-report-v0.1.md    # 一页纸评测报告
```

## 环境准备

### 1. 建虚拟环境

```bash
cd agent-eval
python3 -m venv agent-env
source agent-env/bin/activate
pip install deepeval requests playwright
playwright install chromium
```

### 2. 配凭证（写入 ~/.zshrc）

```bash
export DIFY_API_KEY="app-你的Agent应用密钥"
export ZAI_API_KEY="你的智谱Key"
```

## 运行步骤

### 第 0 步：冒烟

```bash
cd collector
python collect_samples.py --dry-run    # 只跑 3 条（AG-0003 / AG-0201 / AG-0301）
```

### 第 1 步：全量采集

```bash
python collect_samples.py              # 10 个任务，约 10~20 分钟
python behavior_metrics.py             # 耗时 P95、token、成本
```

### 第 2 步：执行验证

```bash
cd ../verifier
python verify_code.py                  # L1/L2/L3 执行验证
```

### 第 3 步：DeepEval 三层判定

```bash
cd ../deepeval
deepeval test run eval_tests.py -k AG-0003   # 先冒烟 1 条
deepeval test run eval_tests.py              # 全量 10 条
```

### 第 4 步：填报告

对照 `report/eval-report-v0.1.md`，按四路来源填数。

## 测评集说明

10 个任务覆盖四种交付形态：

| 形态 | 任务 | 验证手段 |
| --- | --- | --- |
| Python 脚本 | AG-0001/0003/0007/0101/0103 | verify_code.py（py_compile → 跑 → 断言） |
| Web 页面 | AG-0009 | verify_web.py（Playwright 元素交互 + 截图） |
| Skill 调用 | AG-0005 | 轨迹断言（期望调用 generator-testcase-excel） |
| 知识库调用 | AG-0007 | 轨迹断言 + L3 定级断言（S1~S4 口径来自库） |

**为什么只有 10 条**：Agent 评测每跑一条都是 API 调用（token 现结现付），实测单任务 5 万 token / 5 毛钱，20 条成本是 RAG 的几十倍。首轮压到 10 条（每条独立考点），候补池 11 条等跑顺后按 5.4 能力型节奏补回。

## 常见问题

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| `Agent App only supports streaming response mode` (400) | Agent 应用只支持流式 | 采集脚本已用 streaming，不需要改 |
| 采集超时 | Agent 任务分钟级 | `DIFY_API_KEY` 确认后重跑；慢任务属正常 |
| Playwright 报浏览器未安装 | 首次使用 | `playwright install chromium` |
| TaskCompletionMetric 报模型不存在 | ZAI_API_KEY 未配或无效 | 检查环境变量 |
| DeepEval 和 RAGAS 装同一环境报错 | click 依赖互斥 | 一个框架一个环境（本目录 agent-env 独占） |

## 成本参考

实测（png 改名小任务）：单任务 96 秒 / 49,996 token / ¥0.53。全量 10 条一轮约 ¥5，P0 任务的 3 次重复另计。先 `--dry-run` 再全量。
