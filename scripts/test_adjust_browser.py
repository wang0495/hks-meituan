"""Playwright E2E test for CityFlow adjust (SSE)."""
import asyncio
from pathlib import Path

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


async def main():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=EDGE_PATH,
            headless=False,
            args=["--no-sandbox"],
        )
        page = await browser.new_page(viewport={"width": 1400, "height": 900})

        print("[1] Opening CityFlow...")
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.screenshot(path="scripts/test_screenshots/01_loaded.png")
        print("    OK")

        # Submit plan
        input_el = page.locator("#userInput")
        await input_el.fill("珠海一日游")
        print("[2] Planning route...")
        await input_el.press("Enter")

        # Wait for adjust bar
        print("[3] Waiting for plan to complete (up to 120s)...")
        try:
            await page.wait_for_selector("#adjustBar:not(.hidden)", timeout=120000)
            print("    Adjust bar visible!")
        except Exception as e:
            print(f"    FAILED: {e}")
            await page.screenshot(path="scripts/test_screenshots/02_plan_failed.png")
            await browser.close()
            return

        step_count_before = await page.locator(".step-card").count()
        print(f"    Route steps before adjust: {step_count_before}")
        await page.screenshot(path="scripts/test_screenshots/02_plan_done.png")

        # Record chat content BEFORE clicking adjust
        chat_before = await page.locator("#chatMessages").inner_text()
        msg_count_before = len([m for m in chat_before.split("CITYFLOW") if m.strip()])
        print(f"    Chat messages before adjust: ~{msg_count_before}")

        # Click adjust
        print("[4] Clicking '🐢 放慢'...")
        await page.locator("text=🐢 放慢").click()
        await page.screenshot(path="scripts/test_screenshots/03_clicked.png")

        # Wait for adjust to complete
        # We look for the typing indicator to DISAPPEAR (meaning result arrived)
        # OR for a new system message after the user message
        print("[5] Waiting for adjust SSE (up to 180s)...")
        adjust_completed = False
        adjust_failed = False
        last_phase = ""

        for i in range(36):  # 36 x 5s = 180s
            await asyncio.sleep(5)
            elapsed = (i + 1) * 5

            # Check for typing indicator visibility
            typing_visible = await page.locator(".typing-indicator").is_visible()

            # Get current chat
            chat_now = await page.locator("#chatMessages").inner_text()
            new_content = chat_now[len(chat_before):]  # content added after adjust click

            # Check for progress phases
            if "正在重新规划路线" in new_content:
                # Extract elapsed time from message
                idx = new_content.rfind("已耗时")
                if idx >= 0:
                    last_phase = new_content[idx:idx+20]
                    print(f"    [{elapsed}s] Phase: {last_phase}")

            # Check if adjust completed:
            # 1. Typing indicator gone AND
            # 2. New system messages appeared after user message
            if not typing_visible and new_content.strip():
                # Check for new step cards (route was updated)
                step_count_after = await page.locator(".step-card").count()
                if step_count_after > 0:
                    adjust_completed = True
                    print(f"    [{elapsed}s] Adjust completed! Steps: {step_count_after}")
                    break

            # Check for error
            if "❌" in new_content and "调整" in new_content:
                adjust_failed = True
                print(f"    [{elapsed}s] Adjust FAILED: {new_content[-100:]}")
                break

            if i % 6 == 5:
                step_count_after = await page.locator(".step-card").count()
                print(f"    [{elapsed}s] Still waiting... (typing={typing_visible}, steps={step_count_after})")

        await page.screenshot(path="scripts/test_screenshots/04_result.png")

        # Final report
        chat_final = await page.locator("#chatMessages").inner_text()
        new_content = chat_final[len(chat_before):]
        step_count_after = await page.locator(".step-card").count()

        print()
        print("=" * 60)
        print("FINAL REPORT")
        print("=" * 60)
        print(f"  Steps before: {step_count_before}")
        print(f"  Steps after:  {step_count_after}")
        print(f"  Adjust completed: {adjust_completed}")
        print(f"  Adjust failed:    {adjust_failed}")
        print(f"  New chat content: {new_content[-200:]}")
        print("=" * 60)

        await page.screenshot(path="scripts/test_screenshots/05_final.png")
        await browser.close()


if __name__ == "__main__":
    Path("scripts/test_screenshots").mkdir(exist_ok=True)
    asyncio.run(main())
