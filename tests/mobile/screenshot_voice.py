"""
截图语音界面 (http://localhost:3001)
用 Playwright 模拟移动端视口，验证 UI 元素。
"""

import os
from playwright.sync_api import sync_playwright

VOICE_URL = "http://localhost:3001"
SCREENSHOT_PATH = "/tmp/voice_ui_screenshot.png"

def capture_voice_ui():
    with sync_playwright() as p:
        # 启动浏览器（非 headless 模式以便调试）
        browser = p.chromium.launch(headless=True)
        
        # 模拟 iPhone 14 视口
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            is_mobile=True,
            has_touch=True
        )
        
        page = context.new_page()
        
        # 导航到语音界面
        print(f"🌐 导航到 {VOICE_URL}")
        page.goto(VOICE_URL, wait_until="networkidle", timeout=15000)
        
        # 等待页面渲染
        page.wait_for_timeout(2000)
        
        # 截图
        page.screenshot(path=SCREENSHOT_PATH, full_page=True)
        print(f"📸 截图保存到: {SCREENSHOT_PATH}")
        
        # 验证 UI 元素
        print("\n=== UI 元素验证 ===")
        
        # 1. 页面标题
        title = page.title()
        print(f"✓ 页面标题: {title}")
        
        # 2. 检查主要文本内容
        body_text = page.inner_text("body")
        
        if "希露菲" in body_text:
            print("✓ 找到标题「希露菲」")
        else:
            print("✗ 未找到标题「希露菲」")
        
        if "按住说话" in body_text or "松开发送" in body_text:
            print("✓ 找到副标题「按住说话 · 松开发送」")
        else:
            print("✗ 未找到副标题")
        
        if "有什么需要我帮忙的吗" in body_text:
            print("✓ 找到欢迎消息「有什么需要我帮忙的吗？」")
        else:
            print("✗ 未找到欢迎消息")
        
        # 3. 检查麦克风按钮
        mic_buttons = page.query_selector_all("button")
        print(f"✓ 页面中找到 {len(mic_buttons)} 个按钮")
        
        # 4. 检查下拉选择器
        selects = page.query_selector_all("select")
        if selects:
            print(f"✓ 找到 {len(selects)} 个下拉选择器")
            for i, select in enumerate(selects):
                options = select.query_selector_all("option")
                print(f"  - 选择器 {i+1}: {len(options)} 个选项")
                for j, opt in enumerate(options[:5]):  # 只显示前5个
                    print(f"    • {opt.inner_text()}")
        else:
            print("✗ 未找到下拉选择器")
        
        # 5. 页面完整文本内容（用于调试）
        print("\n=== 页面完整内容 ===")
        print(body_text[:1000])  # 只显示前1000字符
        
        # 6. 检查 CSS 样式（暗色主题）
        bg_color = page.evaluate("window.getComputedStyle(document.body).backgroundColor")
        print(f"\n✓ 页面背景色: {bg_color}")
        
        browser.close()
        
        return SCREENSHOT_PATH

if __name__ == "__main__":
    screenshot_path = capture_voice_ui()
    print(f"\n✅ 完成！截图已保存到: {screenshot_path}")
    print("用以下命令查看截图:")
    print(f"  open {screenshot_path}")
