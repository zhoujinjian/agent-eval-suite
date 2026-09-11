# -*- coding: utf-8 -*-
"""评测侧独立实现的核对逻辑（与 Agent 的实现互为独立）——教程 4.3 节。"""
WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
MAP = "10X98765432"


def id_checksum_valid(id17_plus: str) -> bool:
    """GB 11643 校验位核对：前 17 位加权和模 11 映射校验位"""
    if len(id17_plus) != 18:
        return False
    total = sum(int(c) * w for c, w in zip(id17_plus[:17], WEIGHTS))
    return MAP[total % 11] == id17_plus[-1].upper()


def check_id(stdout: str, workdir: str = ".") -> bool:
    """AG-0101 的 L3 断言入口：从输出和产物文件里抓 18 位身份证号逐条核对"""
    import re
    from pathlib import Path
    ids = set(re.findall(r"\d{17}[\dXx]", stdout))
    for f in Path(workdir).glob("*.csv"):
        ids |= set(re.findall(r"\d{17}[\dXx]", f.read_text(encoding="utf-8", errors="ignore")))
    return len(ids) >= 5 and all(id_checksum_valid(i) for i in ids)


def register():
    """把核对函数注入 L3 断言的求值上下文"""
    return {"check_id": check_id, "id_checksum_valid": id_checksum_valid}
