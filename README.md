# agent-eval-suite

《AI 大模型测评体系》系列的**配套评测代码仓库**。每个子目录是一类被测应用的完整评测项目（测评集 + 评测脚本 + 实测报告），与系列教程一一对应，拿到手即可运行。

## 仓库结构

| 子目录 | 被测对象 | 配套教程 | 状态 |
| --- | --- | --- | --- |
| [rag-eval/](./rag-eval) | Dify「测试规范问答助手」（本地私有化 + 知识库，RAG 应用） | 第 12 篇《RAG 项目评测实战》 | ✅ v0.1 基线已产出 |
| agent-eval/ | Agent 应用（任务级用例、mock 工具环境、轨迹评分） | 第 13 篇（规划中） | 🚧 敬请期待 |

## 快速开始

```bash
git clone https://github.com/zhoujinjian/agent-eval-suite.git
cd agent-eval-suite/rag-eval
```

后续三步见 [rag-eval/README.md](./rag-eval/README.md)：

1. 环境准备：Python 3.10+ / Node 22+ / 本地 Dify（被测系统），RAGAS 单独虚拟环境
2. 配两个凭证（环境变量，见下）
3. `./run_all.sh` 一键串联断言评测 → 采集 → 检索层指标 → 行为类指标 → RAGAS

## 安全说明

**本仓库不含任何密钥、账号或凭证**，已做提交前扫描。所有凭证一律通过环境变量注入：

```bash
export DIFY_API_KEY=app-你的Dify应用密钥   # 被测应用的 API Key
export ZAI_API_KEY=你的智谱Key             # llm-rubric / RAGAS 裁判模型
```

`*.env`、虚拟环境、缓存均已列入 `.gitignore`。请勿以任何形式把密钥提交进仓库。

## 版本基线

| Tag | 说明 |
| --- | --- |
| `rag-eval-v0.1` | rag-eval 第一轮基线：dataset v0.1（20 条）+ 全量执行数据 + 评测报告（门禁结论：不过，含 3 条 bad case 与修复清单），详见 [rag-eval/report/eval-report-v0.1.md](./rag-eval/report/eval-report-v0.1.md) |

## 相关教程

- 《AI 大模型测评体系》系列：测评集建设（03）、指标（04）、评分器（05）、Promptfoo（07）、RAGAS（09）、Langfuse（11）、RAG 项目评测实战（12，本仓库 rag-eval 的由来）
- 《Dify 实战系列》第 2、5 讲：被测系统「测试规范问答助手」的搭建过程
