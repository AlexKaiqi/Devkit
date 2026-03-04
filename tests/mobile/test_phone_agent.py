"""
手机操作 Agent 全流程测试

模拟用户指令 → Agent 理解当前屏幕 → 规划操作 → 执行 → 验证结果。
演示 UIAutomator 结构化定位 + Gemini 视觉理解 + ADB 操作的组合。

用法：
    .venv/bin/python tests/mobile/test_phone_agent.py
"""

import base64
import json
import os
import sys
import time

import requests
from android_mcp.mobile.service import Mobile

API_KEY = os.environ.get("LLM_API_KEY", "")
BASE_URL = os.environ.get("LLM_BASE_URL", "")
VISION_MODEL = os.environ.get("VISION_MODEL", "gemini-2.5-flash-nothinking")
DEVICE = os.environ.get("ANDROID_DEVICE", "emulator-5554")


def gemini_chat(prompt: str, image_b64: str | None = None, max_tokens=500) -> str:
    content = [{"type": "text", "text": prompt}]
    if image_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}})
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": VISION_MODEL, "messages": [{"role": "user", "content": content}], "max_tokens": max_tokens},
        timeout=30,
    )
    r = resp.json()
    if "error" in r:
        raise RuntimeError(f"LLM error: {r['error']}")
    return r["choices"][0]["message"]["content"]


def get_screen_state(mobile: Mobile) -> tuple[str, str, list]:
    """获取当前屏幕状态：UI 树文本 + 截图 base64 + 元素列表"""
    state = mobile.get_state(use_vision=True, as_base64=True)
    elements = []
    for i, e in enumerate(state.tree_state.interactive_elements):
        elements.append({
            "id": i,
            "name": e.name,
            "type": e.class_name.split(".")[-1],
            "center": [e.coordinates.x, e.coordinates.y],
        })
    tree_text = state.tree_state.to_string()
    return tree_text, state.screenshot, elements


def plan_action(user_goal: str, elements: list, screenshot_b64: str) -> dict:
    """让 Gemini 根据屏幕状态规划下一步操作"""
    elements_str = json.dumps(elements, ensure_ascii=False, indent=2)
    prompt = f"""你是一个手机操作 Agent。用户目标是：「{user_goal}」

当前屏幕上的可交互元素列表（含精确坐标）：
{elements_str}

同时附上了当前屏幕截图供参考。

请决定下一步操作。用 JSON 回答，格式：
{{"action": "click"|"type"|"swipe"|"press"|"done"|"wait", "target_id": 元素ID, "text": "输入内容(type时)", "reason": "为什么做这一步"}}

判断规则：
- 如果目标应用已打开、目标页面已加载，action 设为 "done"，不要重复操作
- 如果看到 WebView 已显示目标网站内容（如标题、菜单等），说明页面已加载，应该 "done"
- 不要反复点击地址栏和重新输入 URL
- 每一步只执行一个操作
只返回 JSON，不要解释。"""

    result = gemini_chat(prompt, screenshot_b64, max_tokens=300)
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(result)


def execute_action(device, action: dict, elements: list):
    """执行操作"""
    act = action["action"]
    if act == "click":
        tid = action.get("target_id", 0)
        if tid < len(elements):
            x, y = elements[tid]["center"]
        else:
            x, y = 540, 1200
        device.click(x, y)
        return f"点击 ({x},{y}) - {elements[tid]['name'] if tid < len(elements) else '?'}"
    elif act == "type":
        text = action.get("text", "")
        tid = action.get("target_id", 0)
        if tid < len(elements):
            x, y = elements[tid]["center"]
            device.click(x, y)
            time.sleep(0.5)
        device.clear_text()
        device.send_keys(text=text)
        return f"输入 \"{text}\" 到 {elements[tid]['name'] if tid < len(elements) else '?'}"
    elif act == "press":
        button = action.get("text", action.get("button", "enter"))
        device.press(button)
        return f"按键 {button}"
    elif act == "swipe":
        device.swipe(540, 1500, 540, 800)
        return "向上滑动"
    elif act == "wait":
        time.sleep(2)
        return "等待 2 秒"
    return f"未知操作: {act}"


def verify_result(user_goal: str, screenshot_b64: str) -> tuple[bool, str]:
    """让 Gemini 验证目标是否完成"""
    prompt = f"""用户的目标是：「{user_goal}」

请查看当前手机屏幕截图，判断目标是否已完成。
用 JSON 回答：{{"completed": true|false, "description": "当前屏幕状态描述"}}
只返回 JSON。"""

    result = gemini_chat(prompt, screenshot_b64, max_tokens=200)
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    parsed = json.loads(result)
    return parsed.get("completed", False), parsed.get("description", "")


def run_agent(user_goal: str, max_steps=8):
    """运行手机操作 Agent"""
    print(f"\n{'=' * 60}")
    print(f"  用户指令: {user_goal}")
    print(f"  模型: {VISION_MODEL}")
    print(f"{'=' * 60}")

    mobile = Mobile(device=DEVICE)
    device = mobile.get_device()

    for step in range(1, max_steps + 1):
        print(f"\n── 步骤 {step}/{max_steps} ──")

        tree_text, screenshot_b64, elements = get_screen_state(mobile)
        print(f"  屏幕元素: {len(elements)} 个")
        for e in elements[:8]:
            print(f"    [{e['id']}] {e['name'][:30]} ({e['type']}) @ {e['center']}")
        if len(elements) > 8:
            print(f"    ... 还有 {len(elements) - 8} 个")

        action = plan_action(user_goal, elements, screenshot_b64)
        print(f"  决策: {action['action']} → {action.get('reason', '')}")

        if action["action"] == "done":
            print(f"\n  Agent 判断目标已完成")
            break

        result = execute_action(device, action, elements)
        print(f"  执行: {result}")

        time.sleep(1.5)
    else:
        print(f"\n  达到最大步数 {max_steps}")

    print(f"\n── 验证结果 ──")
    time.sleep(1)
    _, final_screenshot, _ = get_screen_state(mobile)
    completed, description = verify_result(user_goal, final_screenshot)
    status = "✓ 完成" if completed else "△ 未完成"
    print(f"  [{status}] {description}")

    return completed


def main():
    if not API_KEY or not BASE_URL:
        print("需要设置 LLM_API_KEY 和 LLM_BASE_URL")
        sys.exit(1)

    tasks = [
        "打开 Chrome 浏览器",
        "在 Chrome 地址栏输入 github.com 并访问",
    ]

    print("=" * 60)
    print("  手机操作 Agent 全流程测试")
    print("=" * 60)

    results = []
    for task in tasks:
        try:
            ok = run_agent(task, max_steps=6)
            results.append((task, ok))
        except Exception as e:
            print(f"\n  [✗] 异常: {e}")
            results.append((task, False))

    print(f"\n{'=' * 60}")
    print("  总结")
    print(f"{'=' * 60}")
    for task, ok in results:
        s = "✓" if ok else "✗"
        print(f"  [{s}] {task}")

    passed = sum(1 for _, ok in results if ok)
    print(f"\n  {passed}/{len(results)} 通过")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
