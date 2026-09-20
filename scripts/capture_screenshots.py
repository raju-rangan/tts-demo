#!/usr/bin/env python3
"""
Automated Chrome DevTools Protocol (CDP) script to capture all 7 screenshots for USER_GUIDE.md.
Connects directly to the running Chrome instance on port 9222 and controls the application
running at http://127.0.0.1:8000.
"""

import asyncio
import base64
import json
import os
import urllib.request
import websockets

SCREENSHOT_DIR = "/Users/rrangan/Documents/customers/tts-demo/docs/images"

async def main():
    try:
        req = urllib.request.urlopen("http://[::1]:9222/json/list")
        targets = json.loads(req.read().decode())
    except Exception as e:
        print(f"Error connecting to Chrome on [::1]:9222: {e}")
        return 1

    page_target = next((t for t in targets if t.get("type") == "page"), None)
    if not page_target:
        print("No page target found in Chrome DevTools.")
        return 1

    ws_url = page_target["webSocketDebuggerUrl"]
    print(f"Connecting to CDP WebSocket: {ws_url}")

    async with websockets.connect(ws_url, max_size=30 * 1024 * 1024) as ws:
        cmd_id = 1

        async def send_cmd(method, params=None):
            nonlocal cmd_id
            cid = cmd_id
            cmd_id += 1
            await ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == cid:
                    if "error" in msg:
                        raise RuntimeError(f"CDP error for {method}: {msg['error']}")
                    return msg.get("result")

        async def eval_js(expr):
            res = await send_cmd("Runtime.evaluate", {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": True
            })
            return res.get("result", {}).get("value")

        async def capture(filename, width=1440, height=900, scale=2):
            await send_cmd("Emulation.setDeviceMetricsOverride", {
                "width": width,
                "height": height,
                "deviceScaleFactor": scale,
                "mobile": False
            })
            await asyncio.sleep(0.6)
            res = await send_cmd("Page.captureScreenshot", {"format": "png"})
            img_data = base64.b64decode(res["data"])
            filepath = os.path.join(SCREENSHOT_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(img_data)
            print(f"✅ Captured {filename} ({len(img_data):,} bytes)")

        await send_cmd("Page.enable")
        await send_cmd("Runtime.enable")

        # Navigate to app
        print("Navigating to http://127.0.0.1:8000...")
        await send_cmd("Page.navigate", {"url": "http://127.0.0.1:8000"})
        await asyncio.sleep(3.0)

        # -------------------------------------------------------------
        # 1. Login Screen / Workspace Persona Selector Hub
        # -------------------------------------------------------------
        print("1. Capturing 01_login_screen.png...")
        await eval_js("""
            showProfileSelect('local-dev@apexbank.com');
            if (window.lucide) lucide.createIcons();
        """)
        await asyncio.sleep(1.0)
        await capture("01_login_screen.png", width=1440, height=900)

        # -------------------------------------------------------------
        # 2. Studio Dashboard (Sarah Jenkins)
        # -------------------------------------------------------------
        print("2. Capturing 02_studio_dashboard.png...")
        await eval_js("""
            (async () => {
                await choosePersona('creator');
                if (typeof closeCreateJobModal === 'function') closeCreateJobModal();
                if (typeof closeBulkJobModal === 'function') closeBulkJobModal();
                if (typeof closeDetailModal === 'function') closeDetailModal();
                if (typeof closeFinOpsDrawer === 'function') closeFinOpsDrawer();
                await loadJobs();
                await loadStats();
                if (window.lucide) lucide.createIcons();
            })()
        """)
        await asyncio.sleep(2.0)
        await capture("02_studio_dashboard.png", width=1440, height=900)

        # -------------------------------------------------------------
        # 3. Live 5-Stage Synthesis Stepper
        # -------------------------------------------------------------
        print("3. Capturing 03_progress_synthesis.png...")
        await eval_js("""
            (async () => {
                const sampleRunningJob = {
                    job_id: 'job_synth_preview',
                    status: 'RUNNING',
                    created_at: new Date().toISOString(),
                    article_title: 'High-Yield Savings Accounts vs. Certificates of Deposit (CDs): A Financial Guide for Retail Banking Customers',
                    persona_name: 'Retail Banking Guide (External Customers | Voice: Sulafat)',
                    audience: 'External Customers',
                    audience_prefix: 'external/audio/',
                    transcript: 'When planning your short-to-medium-term savings strategy, two of the most secure instruments available are High-Yield Savings Accounts (HYSA) and Certificates of Deposit (CDs)...',
                    word_count: 227,
                    voice_customization: 'Speak with an articulate, reassuring retail banking demeanor. Enunciate "High-Yield" and acronyms FDIC, APY, CD with precision.',
                    target_url: null,
                    progress_stage: 'SYNTHESIZING',
                    current_turn: 1,
                    total_turns: 2,
                    turns_completed: 0,
                    latency_seconds: 14.8
                };
                await openJobDetail('job_synth_preview', sampleRunningJob);
                if (window.lucide) lucide.createIcons();
            })()
        """)
        await asyncio.sleep(1.5)
        await capture("03_progress_synthesis.png", width=1440, height=900)

        # -------------------------------------------------------------
        # 4. Audio Player & Multimodal Quality Scorecard
        # -------------------------------------------------------------
        print("4. Capturing 04_audio_player_scorecard.png...")
        await eval_js("""
            (async () => {
                await loadJobs();
                const target = ALL_JOBS.find(j => j.status === 'COMPLETED' && j.overall_score >= 4.0) || ALL_JOBS[0];
                if (target) {
                    await openJobDetail(target.job_id);
                }
                if (window.lucide) lucide.createIcons();
                const scrollable = document.querySelector('#jobDetailModal .overflow-y-auto');
                if (scrollable) scrollable.scrollTop = 0;
            })()
        """)
        await asyncio.sleep(1.5)
        await capture("04_audio_player_scorecard.png", width=1440, height=1050)

        # -------------------------------------------------------------
        # 5. Slide-Over Enterprise FinOps Drawer
        # -------------------------------------------------------------
        print("5. Capturing 05_finops_drawer.png...")
        await eval_js("""
            closeDetailModal();
            openFinOpsDrawer();
            if (window.lucide) lucide.createIcons();
        """)
        await asyncio.sleep(1.5)
        await capture("05_finops_drawer.png", width=1440, height=900)

        # -------------------------------------------------------------
        # 6. Bulk URL Ingestion & Processing
        # -------------------------------------------------------------
        print("6. Capturing 06_bulk_url_processing.png...")
        await eval_js("""
            closeFinOpsDrawer();
            openBulkJobModal();
            document.getElementById('inputBulkUrls').value = [
                'https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm',
                'https://www.fdic.gov/news/press-releases/2024/pr24012.html',
                'https://en.wikipedia.org/wiki/Certificate_of_deposit'
            ].join('\\n');
            document.getElementById('inputBulkVoiceCustomization').value = 'Speak with an authoritative, measured cadence on market insights and policy changes.';
            updateBulkUrlStats();
            if (window.lucide) lucide.createIcons();
        """)
        await asyncio.sleep(1.5)
        await capture("06_bulk_url_processing.png", width=1440, height=900)

        # -------------------------------------------------------------
        # 7. Executive Compliance & Governance Dashboard (David Chen)
        # -------------------------------------------------------------
        print("7. Capturing 07_auditor_dashboard.png...")
        await eval_js("""
            (async () => {
                closeBulkJobModal();
                await choosePersona('auditor');
                switchAuditorSubView('dashboard');
                if (window.lucide) lucide.createIcons();
            })()
        """)
        await asyncio.sleep(2.5)  # Chart.js animations
        await capture("07_auditor_dashboard.png", width=1440, height=1100)

        print("🎉 All 7 screenshots captured successfully!")
    return 0

if __name__ == "__main__":
    asyncio.run(main())
