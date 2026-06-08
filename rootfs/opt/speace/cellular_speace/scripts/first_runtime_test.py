"""SPEACE First Controlled Runtime Test — T109 smoke test.

Avvia il monitor + runtime per ~30s, verifica stato, dialogue,
checkpoint, narrative. Usa solo librerie built-in + uvicorn.
"""

import asyncio
import json
import time
import urllib.request

import uvicorn


async def fetch(url: str, data: bytes = None, method: str = "GET") -> dict:
    def _fetch() -> dict:
        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    return await asyncio.to_thread(_fetch)


async def main() -> None:
    print("=" * 64)
    print("SPEACE First Controlled Runtime Test (T109)")
    print("=" * 64)

    # ------------------------------------------------------------------ #
    # 1. Start server
    # ------------------------------------------------------------------ #
    config = uvicorn.Config(
        "speace_core.monitoring.dashboard_api:app",
        host="127.0.0.1",
        port=8787,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    print("\n[1/7] Waiting for server...")
    for _ in range(10):
        try:
            health = await fetch("http://127.0.0.1:8787/api/health")
            if health.get("status") == "ok":
                print(f"Server ready. SPEACE version: {health.get('speace_version', '?')}")
                break
        except Exception:
            pass
        await asyncio.sleep(1)
    else:
        print("ERROR: Server did not start in time.")
        server.should_exit = True
        await server_task
        return

    # ------------------------------------------------------------------ #
    # 2. Start runtime
    # ------------------------------------------------------------------ #
    print("\n[2/7] Starting runtime...")
    start_result = await fetch(
        "http://127.0.0.1:8787/api/runtime/start",
        data=b"{}",
        method="POST",
    )
    print(f"  Runtime state: {start_result.get('state', 'unknown')}")
    print(f"  Recovery: {start_result.get('recovery', {}).get('status', 'unknown')}")
    resume = start_result.get('resume_narrative', '')
    if resume:
        print(f"  Resume: {resume}")

    # ------------------------------------------------------------------ #
    # 3. Poll for 30 seconds
    # ------------------------------------------------------------------ #
    print("\n[3/7] Polling runtime state (30s)...")
    for i in range(3):
        await asyncio.sleep(10)
        try:
            state = await fetch("http://127.0.0.1:8787/api/runtime/state")
            tick = state.get('tick_count', 0)
            rt_state = state.get('state', 'unknown')
            health = state.get('health', {}).get('health_score', 'unknown')
            phase = state.get('circadian', {}).get('phase', 'unknown')
            lifecycle = state.get('lifecycle', {}).get('current_state', 'unknown')
            print(f"  t+{(i+1)*10:3d}s | tick={tick:4d} | state={rt_state:8s} | health={health} | phase={phase} | lifecycle={lifecycle}")
        except Exception as e:
            print(f"  t+{(i+1)*10:3d}s | error: {e}")

    # ------------------------------------------------------------------ #
    # 4. Send dialogue
    # ------------------------------------------------------------------ #
    print("\n[4/7] Sending dialogue message...")
    dialogue_msg = (
        "Ciao SPEACE. Questa è la tua prima sessione di runtime continuo controllato. "
        "Osserva il tuo stato, registra l'esperienza e non eseguire azioni autonome."
    )
    dialogue_result = await fetch(
        "http://127.0.0.1:8787/api/dialogue/message",
        data=json.dumps({"message": dialogue_msg}).encode(),
        method="POST",
    )
    response_text = dialogue_result.get('message', 'no response')
    print(f"  SPEACE: {response_text}")

    # ------------------------------------------------------------------ #
    # 5. Halt runtime
    # ------------------------------------------------------------------ #
    print("\n[5/7] Halting runtime...")
    halt_result = await fetch(
        "http://127.0.0.1:8787/api/runtime/control",
        data=json.dumps({"action": "halt"}).encode(),
        method="POST",
    )
    print(f"  Halt result: {halt_result.get('state', 'unknown')}")
    await asyncio.sleep(3)

    # ------------------------------------------------------------------ #
    # 6. Check checkpoints
    # ------------------------------------------------------------------ #
    print("\n[6/7] Checking checkpoints...")
    try:
        checkpoints = await fetch("http://127.0.0.1:8787/api/runtime/checkpoints?limit=5")
        cps = checkpoints.get('checkpoints', [])
        print(f"  Checkpoints found: {len(cps)}")
        for cp in cps[:3]:
            ts = cp.get('timestamp', 0)
            tick = cp.get('orchestrator', {}).get('current_tick', '?')
            print(f"    - tick {tick} at {time.strftime('%H:%M:%S', time.localtime(ts))}")
    except Exception as e:
        print(f"  Checkpoint check error: {e}")

    # ------------------------------------------------------------------ #
    # 7. Check experience timeline
    # ------------------------------------------------------------------ #
    print("\n[7/7] Checking experience timeline...")
    try:
        timeline = await fetch("http://127.0.0.1:8787/api/experience/timeline?hours=1&limit=20")
        events = timeline.get('events', [])
        print(f"  Narrative events: {len(events)}")
        for ev in events[-5:]:
            etype = ev.get('event_type', '?')
            desc = ev.get('description', '')[:60]
            print(f"    - [{etype}] {desc}")
    except Exception as e:
        print(f"  Timeline check error: {e}")

    # ------------------------------------------------------------------ #
    # Stop server
    # ------------------------------------------------------------------ #
    print("\nStopping server...")
    server.should_exit = True
    await server_task
    print("Test complete.")


if __name__ == "__main__":
    asyncio.run(main())
