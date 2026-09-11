# rag-eval · 测试规范问答助手评测项目

> `agent-eval-suite` 的子项目之一，《AI 大模型测评体系》第 12 篇（RAG 项目评测实战）的配套可运行代码。被测对象是 Dify 系列第 2、5 讲搭起来的「测试规范问答助手」Chatflow（本地私有化 Dify + 测试规范知识库）。

```
rag-eval/
├── dataset/
│   └── dataset.csv            # 20 条测评集（高频 7 / 边界 5 / 拒答 3 / 对抗 5）
├── promptfoo/
│   └── promptfooconfig.yaml   # 断言层评测：20 条全量，规则断言 + llm-rubric
├── collector/
│   ├── collect_samples.py     # 采集：调 Dify API，拿回答/检索/时延/token → samples.json
│   ├── retrieval_metrics.py   # 检索层：命中率@5、MRR、拒答误召回
│   └── behavior_metrics.py    # 行为类：P95 时延、token 消耗
├── ragas/
│   └── rag_eval.py            # RAGAS：忠实度、上下文召回、上下文精确率
├── report/
│   ├── eval-report-v0.1.md    # 第一轮基线评测报告（一页纸）
│   ├── retrieval-metrics.json # 检索层指标明细
│   ├── behavior-metrics.json  # 行为类指标明细
│   └── ragas-scores.csv       # RAGAS 逐条分数
└── run_all.sh                 # 一键串联五步
```

## 一、环境准备

### 1. 基础依赖

| 依赖 | 版本要求 | 检查命令 | 用在哪 |
| --- | --- | --- | --- |
| Python | 3.10+（RAGAS 要求 3.9+） | `python3 --version` | 采集、指标、RAGAS |
| Node.js | 22+ | `node -v` | Promptfoo（npx 直接跑，无需安装） |
| Docker + Dify | 第 2 讲部署的 1.16.x | `docker compose ps` 全 running | 被测系统 |

### 2. Python 环境（一条重要原则：一个框架一个环境）

采集脚本只依赖 `requests`，用哪个 Python 都行；RAGAS 必须单独虚拟环境（09 篇实测：它与 DeepEval 的 click 依赖互斥，混装必出问题）。

从零新建（推荐，在本目录内）：

```bash
cd rag-eval
python3 -m venv ragas-env
source ragas-env/bin/activate
pip install ragas requests
# 09 篇踩过的坑：RAGAS 0.4.x 没锁 LangChain 版本上限，新环境要降级修复
pip install "langchain<1.0" "langchain-core<1.0" "langchain-community<0.4" "langchain-openai<1.0"
```

跟过 09 篇教程、`ai_project` 目录下已有 `ragas-env` 的，可以直接复用，`run_all.sh` 会自动探测（本目录 `ragas-env` 优先，其次上两级目录的 09 篇环境）。

### 3. 凭证（两个 Key，都不进 Git）

```bash
# Dify 应用的 API 密钥（应用编排页左侧「API 访问」→「API 密钥」→ 创建，app- 开头）
export DIFY_API_KEY=app-你的密钥

# 智谱 Key（bigmodel.cn 申请），llm-rubric 裁判和 RAGAS 裁判共用
export ZAI_API_KEY=你的智谱Key

# 可选：Dify 端口改过的话（比如映射到 3000）
# export DIFY_BASE_URL=http://127.0.0.1:3000
```

## 二、运行步骤（按顺序）

### 第 0 步：冒烟，确认被测接口活着

```bash
curl -s -m 90 -X POST 'http://127.0.0.1/v1/chat-messages' \
  -H "Authorization: Bearer $DIFY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"inputs":{},"query":"S1 缺陷的定义是什么？","response_mode":"blocking","conversation_id":"","user":"eval-runner"}' | jq .
```

看到 `answer`、`metadata.retriever_resources`、`metadata.usage` 三个字段就绪即可。注意 blocking 单次要 10~20 秒，超时别给太短。

### 第 1 步：断言层评测（Promptfoo）

```bash
cd promptfoo
npx promptfoo@latest eval -c promptfooconfig.yaml   # 跑 20 条
npx promptfoo@latest view                           # 打开本地网页报告（localhost:15500）
```

通过率低于 threshold（0.9）时命令以非零码退出，这是给 CI 门禁用的；本地看报告不受影响。裁判（llm-rubric）已统一配成智谱 glm-5.3，需要 `ZAI_API_KEY`。

### 第 2 步：采集（回答 + 检索 + 时延 + token）

```bash
cd ../collector
python3 collect_samples.py --dry-run    # 先跑 3 条冒烟，确认字段都对
python3 collect_samples.py              # 全量 20 条，约 5 分钟
```

产出 `samples.json`：每条带剥掉 think 后的回答、检回片段（文档名/排名/分数/原文）、时延、token。

### 第 3 步：检索层指标 + 行为类指标

```bash
python3 retrieval_metrics.py    # 命中率@5、MRR、拒答误召回
python3 behavior_metrics.py     # P95 时延、token
```

产出 `report/retrieval-metrics.json`、`report/behavior-metrics.json`。

### 第 4 步：RAGAS 三指标（在 ragas 环境里跑）

```bash
cd ../ragas
# 用第 2 节新建的环境：
source ../ragas-env/bin/activate
python rag_eval.py
# 或不激活直接用：../ragas-env/bin/python rag_eval.py

# 建议先小批量验证配置再放全量（裁判按 token 计费）：
RAGAS_SMOKE=1 python rag_eval.py
```

产出终端总分 + `report/ragas-scores.csv`（逐条分数）。

### 第 5 步：填报告

对照 `report/eval-report-v0.1.md`（第一轮已填好实测数据，可作为你自己项目的报告范例），换被测系统后按同样四路来源填新报告。

### 一键串联（可选）

```bash
cd rag-eval
./run_all.sh
```

## 三、测评集说明（对齐真实知识库）

`dataset.csv` 的 20 条题是按**实际入库文档**的内容出的，关键锚点（跑之前可自行核对）：

| 参考文档 | 知识库里的真实内容 |
| --- | --- |
| 缺陷分级标准.docx | 缺陷分 S1 致命 / S2 严重 / S3 一般 / S4 轻微四级；S1 定义为系统崩溃、核心功能完全不可用、数据丢失或损坏、阻塞测试进程；标注「S1 默认优先级为 P0」 |
| 提测规范.docx | 8 项前置条件（需求已基线…依赖已确认）+ 提测流程三步（提测申请、冒烟测试、提测确认） |
| 用例编写规范.docx | 场景覆盖占比（正向 40-50%、逆向 20-25%、边界值 10-15%…）、用例要素表 |
| 测试流程总纲.docx | 测试准出标准（执行率 ≥98%、通过率 ≥95%、P0 修复率 100% 无遗留、P2 ≥90%）；线上缺陷处理（恢复后 24 小时内出复盘报告） |

两个设计要点：

- **「参考片段开头」列**是检索层排名匹配的锚，取自真实检回片段的原文开头；留空的行（如准出标准、复盘）按「参考文档名」匹配兜底。你重灌知识库或换文档后，这一列要对新文档原文重新核对，否则命中率会虚低。
- **拒答题三列全空**（参考答案/参考文档/参考片段开头），不是漏填：拒答题不进命中率统计，检索空手而归才是正确行为，它单看「误召回」。

## 四、常见问题

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| 返回里没有 `retriever_resources` | 知识检索节点没接好 / 引用与归属没开 / 用了 streaming | 按教程 1.3 节排查清单查三处 |
| 回答里混着思考过程 | 应用内是思考型模型，answer 带 `<think>` 块 | 采集和断言层已自动剥离，无需处理 |
| 单条请求 10 秒以上 | blocking 模式 + 思考型模型的正常水平 | 正常现象，P95 门禁建议按真实基线与业务方重定 |
| llm-rubric 全部报 JSON 解析失败 | 裁判模型输出格式不稳定 | 换非思考型模型当 grader，或重跑一轮验证稳定性 |
| Promptfoo 裁判报模型不存在 | ZAI_API_KEY 没导出或 Key 无效 | 确认环境变量；裁判配置在 defaultTest 里 |
| RAGAS 报 ModuleNotFoundError: langchain_community... | LangChain 1.x 与 RAGAS 0.4 不兼容 | 执行环境准备里的降级命令 |
| RAGAS 装不进 DeepEval 环境 | click 版本互斥 | 一个框架一个环境，别混装 |
| 指标 nan | 样本检索为空或回答过短 | 看 samples.json 对应条目，属真实失败而非脚本问题 |

## 五、成本参考

全量一轮（20 条）大约：Dify 侧 20 次应用调用（应用内 GLM 计费，实测单条约 1400 token）+ 裁判侧 15 次 llm-rubric + RAGAS 三指标 10 条样本。按智谱计价整轮通常几毛钱量级。养成先 `--dry-run` / `RAGAS_SMOKE` 再全量的习惯。
