# -*- coding: utf-8 -*-
"""Web 交付验证（教程第 13 篇 3.4 节）：Playwright 元素交互断言 + 截图存档。

用法：python verify_web.py <交付的 HTML 文件路径>
前提：pip install playwright && playwright install chromium

本地跑，不烧 Agent token——贵的是 Agent 生成那次 API 调用，验证本身近乎免费。
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "report"


def verify_web(html_file: str, port: int = 18888) -> bool:
    """起本地服务 → Playwright 打开 → 元素交互断言 → 截图存档"""
    import http.server
    import threading

    # 起本地 HTTP 服务
    handler = http.server.SimpleHTTPRequestHandler
    handler.directory = str(Path(html_file).parent)
    server = http.server.HTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(1)

    filename = Path(html_file).name
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # L2：页面不白屏
            page.goto(f"http://127.0.0.1:{port}/{filename}")
            assert page.title() != "", "页面无 title（可能白屏）"

            # L3 断言一：交互后匹配结果正确
            page.fill("#regex-input", r"\d+")
            page.fill("#text-input", "订单号 12345，共 2 件")
            page.click("#test-btn")
            result = page.inner_text("#result")
            assert "12345" in result and "2" in result, f"匹配结果不对: {result}"

            # L3 断言二（反作弊）：换一档输入，结果必须跟着变
            page.fill("#text-input", "没有数字的文本")
            page.click("#test-btn")
            assert "12345" not in page.inner_text("#result"), "换输入结果不变，疑似写死"

            # 截图存档，进报告当证据
            SCREENSHOT_DIR.mkdir(exist_ok=True)
            page.screenshot(path=str(SCREENSHOT_DIR / "ag0009_final.png"))
            browser.close()
        return True
    finally:
        server.shutdown()


if __name__ == "__main__":
    html = sys.argv[1] if len(sys.argv) > 1 else "agent_code.html"
    ok = verify_web(html)
    print("✓ Web 验证通过" if ok else "✗ Web 验证未通过")
    sys.exit(0 if ok else 1)
