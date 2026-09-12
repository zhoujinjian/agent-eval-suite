# -*- coding: utf-8 -*-
"""执行验证器（教程第 13 篇 4.3 节）：把交付的代码在本地真跑，按 L1/L2/L3 断言。

用法：python verify_code.py [samples.json 路径]
产出：终端打印 + report/verify-results.json
"""
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SAMPLES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "collector" / "samples.json"
DATASET = Path(__file__).resolve().parent.parent / "dataset" / "dataset.csv"
REPORT = Path(__file__).resolve().parent.parent / "report" / "verify-results.json"

CODE_RE = re.compile(r"##\s*\d*[、.]?\s*代码(.*?)(?=##\s*\d*[、.]?\s*依赖|##\s*\d*[、.]?\s*使用说明|\Z)", re.S)
FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.S)


def extract_code(answer: str):
    """从交付的「## 代码」段抽代码块，返回 (语言, 代码) 列表"""
    sec = CODE_RE.search(answer)
    if not sec:
        return []
    out = []
    for lang, code in FENCE_RE.findall(sec.group(1)):
        if lang in ("", "text"):
            lang = "python"
        out.append((lang.lower(), code))
    return out


def verify_one(sample: dict, task: dict, workdir: Path) -> dict:
    """对一条样本做 L1/L2/L3 执行验证"""
    lang, src = "", ""
    for l, code in extract_code(sample["response"]):
        lang, src = l, code
        break
    if not src:
        return {"id": sample.get("id", task.get("编号", "?")), "level": task.get("验证级", ""), "pass": False,
                "reason": "未找到「## 代码」代码块"}

    suffix = ".py" if lang in ("python", "py") else ".sh"
    code_file = workdir / f"agent_code{suffix}"
    code_file.write_text(src, encoding="utf-8")

    # ---- L1 语法级 ----
    l1_cmd = ([sys.executable, "-m", "py_compile", str(code_file)] if suffix == ".py"
              else ["bash", "-n", str(code_file)])
    r1 = subprocess.run(l1_cmd, capture_output=True, text=True, timeout=30)
    if r1.returncode != 0:
        return {"id": sample.get("id", task.get("编号", "?")), "level": task.get("验证级", ""), "pass": False,
                "reason": f"L1 语法失败：{r1.stderr[:200]}"}
    if task.get("验证级") in ("L1", "不执行", ""):
        return {"id": sample.get("id", task.get("编号", "?")), "level": "L1", "pass": True, "reason": "语法级通过"}

    # ---- L2/L3 试运行与输出断言 ----
    cmd = (task.get("验证命令", "")
           .replace("{python}", sys.executable)
           .replace("{code_file}", str(code_file)))
    r2 = subprocess.run(cmd, shell=True, cwd=workdir, capture_output=True,
                        text=True, timeout=300)
    result = {"id": sample.get("id", task.get("编号", "?")), "level": task.get("验证级", ""),
              "exit_code": r2.returncode, "stdout": r2.stdout[:500]}
    if r2.returncode != 0:
        result.update({"pass": False, "reason": f"运行失败：{r2.stderr[:200]}"})
        return result
    if task.get("验证级") == "L2":
        result.update({"pass": True, "reason": "试运行通过"})
        return result

    # ---- L3 断言 ----
    from checks import register
    ctx = {"stdout": r2.stdout, "exit_code": r2.returncode, "workdir": str(workdir)}
    try:
        ok = eval(task["验证断言"], {"__builtins__": __builtins__}, {**register(), **ctx})
        result.update({"pass": bool(ok), "reason": "输出断言通过" if ok else "输出断言不满足"})
    except Exception as e:
        result.update({"pass": False, "reason": f"断言执行异常：{e}"})
    return result


def main():
    samples = {s["id"]: s for s in json.loads(SAMPLES.read_text(encoding="utf-8"))}
    tasks = {r["编号"]: r for r in csv.DictReader(open(DATASET, encoding="utf-8-sig"))}
    results = []

    for tid, task in tasks.items():
        if task.get("验证级") == "不执行":
            continue
        sid = tid.split("#")[0]
        if sid not in samples:
            continue
        workdir = Path(tempfile.mkdtemp(prefix="verify_"))
        try:
            results.append(verify_one(samples[sid], task, workdir))
        except subprocess.TimeoutExpired:
            results.append({"id": tid, "pass": False, "reason": "执行超时（300s）"})
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    n = len(results)
    ok = sum(1 for r in results if r.get("pass"))
    if n:
        print(f"执行验证 {n} 条：可运行率 = {ok/n:.0%}")
    for r in results:
        mark = "✓" if r.get("pass") else "✗"
        print(f"  {mark} {r['id']} [{r.get('level')}] {r.get('reason', '')[:60]}")

    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"明细已写入 {REPORT}")


if __name__ == "__main__":
    main()
