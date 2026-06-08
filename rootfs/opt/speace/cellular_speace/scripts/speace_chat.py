#!/usr/bin/env python3
"""speace_chat — Interfaccia terminale per dialogare con SPEACE.

Uso:
    python scripts/speace_chat.py
    python scripts/speace_chat.py --voice   # abilita output vocale
    python scripts/speace_chat.py --runtime # usa il runtime API se disponibile

Comandi speciali:
    /voice      attiva/disattiva output vocale
    /history    mostra ultimi turni di dialogo
    /status     mostra stato organismico (se runtime attivo)
    /speak      pronuncia l'ultima risposta di SPEACE
    /quit       esci
"""

import argparse
import json
import sys
import time
import urllib.request
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.language.dialogue_manager import DialogueManager
from speace_core.cellular_brain.language.speech_output_organ import SpeechOutputOrgan


def _get_local_token() -> str:
    """Recupera il token locale dalle variabili di ambiente o dal runtime."""
    import os
    token = os.environ.get("SPEACE_LOCAL_TOKEN", "")
    if not token:
        # Prova a leggere dal log del runtime
        import warnings
        # Il token viene generato dal dashboard; se non disponibile, usiamo una modalità offline
        return ""
    return token


def _try_runtime_ping(host: str = "127.0.0.1", port: int = 8787) -> bool:
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/api/health", method="GET", timeout=2
        )
        with urllib.request.urlopen(req) as resp:
            return resp.status == 200
    except Exception:
        return False


def _send_runtime_message(
    message: str, host: str = "127.0.0.1", port: int = 8787, token: str = ""
) -> Optional[Dict[str, Any]]:
    try:
        data = json.dumps({"message": message}).encode("utf-8")
        req = urllib.request.Request(
            f"http://{host}:{port}/api/dialogue/message",
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-local-token": token,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _fetch_runtime_state(host: str = "127.0.0.1", port: int = 8787, token: str = "") -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/api/runtime/state",
            headers={"x-local-token": token},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _fetch_runtime_history(host: str = "127.0.0.1", port: int = 8787, token: str = "", limit: int = 5) -> List[Dict[str, Any]]:
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/api/dialogue/history?limit={limit}",
            headers={"x-local-token": token},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("turns", [])
    except Exception:
        return []


def _speak_text(text: str, speech: SpeechOutputOrgan) -> None:
    result = speech.speak(text)
    mode = result.get("mode", "none")
    if mode == "spoken":
        print("  [VOCE: emissione altoparlante completata]")
    elif mode == "printed":
        print("  [VOCE: fallback console (pyttsx3 non disponibile)]")
    elif mode == "muted":
        print("  [VOCE: muto attivo]")
    elif mode == "error":
        print(f"  [VOCE: errore - {result.get('detail', 'unknown')}]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interfaccia terminale per SPEACE")
    parser.add_argument("--voice", action="store_true", help="Abilita output vocale all'avvio")
    parser.add_argument("--runtime", action="store_true", help="Preferisci connessione al runtime")
    args = parser.parse_args()

    voice_enabled = args.voice
    prefer_runtime = args.runtime

    # Inizializza organi
    speech = SpeechOutputOrgan(enabled=True, muted=not voice_enabled)
    dialogue_offline = DialogueManager(speech_organ=speech)

    # Prova a connettersi al runtime
    runtime_available = False
    token = _get_local_token()
    if prefer_runtime or _try_runtime_ping():
        runtime_available = _try_runtime_ping()

    print("=" * 60)
    print("  SPEACE — Interfaccia Terminale di Dialogo")
    print("  Versione: 0.9.0")
    print("=" * 60)
    if runtime_available:
        print("  Modalita: connesso al runtime (http://127.0.0.1:8787)")
    else:
        print("  Modalita: offline (DialogueManager diretto)")
    if voice_enabled:
        print("  Voce: ATTIVA (pyttsx3)")
    else:
        print("  Voce: DISATTIVATA (usa /voice per attivare)")
    print("  Comandi: /voice  /history  /status  /speak  /quit")
    print("-" * 60)
    print()

    last_speace_message = ""

    while True:
        try:
            user_input = input("Tu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nUscita...")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "exit", "esci"):
            print("SPEACE: A presto, Roberto. La sessione e terminata.")
            if voice_enabled:
                _speak_text("A presto, Roberto. La sessione e terminata.", speech)
            break

        if user_input.lower() == "/voice":
            voice_enabled = not voice_enabled
            speech.set_mute(not voice_enabled)
            stato = "ATTIVA" if voice_enabled else "DISATTIVATA"
            print(f"SPEACE: Voce {stato}.")
            if voice_enabled:
                _speak_text(f"Voce {stato}.", speech)
            continue

        if user_input.lower() == "/speak":
            if last_speace_message:
                _speak_text(last_speace_message, speech)
            else:
                print("SPEACE: Nessuna risposta precedente da pronunciare.")
            continue

        if user_input.lower() == "/history":
            if runtime_available:
                turns = _fetch_runtime_history(token=token, limit=5)
            else:
                turns = dialogue_offline.history(limit=5)
            print("  --- Ultimi turni ---")
            for t in turns:
                speaker = t.get("speaker", "?")
                msg = t.get("message", "")
                print(f"  [{speaker}] {msg}")
            print("  --------------------")
            continue

        if user_input.lower() == "/status":
            if runtime_available:
                state = _fetch_runtime_state(token=token)
                if state:
                    print(f"  Stato runtime: {state.get('state', 'unknown')}")
                    print(f"  Ticks: {state.get('tick_count', 0)}")
                    print(f"  Uptime: {state.get('uptime_seconds', 0):.0f}s")
                    health = state.get("health", {})
                    print(f"  Health score: {health.get('health_score', 0.0)}")
                    print(f"  Eccezioni: {health.get('total_exceptions', 0)}")
                else:
                    print("  Stato runtime: non disponibile")
            else:
                print("  Stato runtime: offline")
            continue

        # Invio messaggio a SPEACE
        if runtime_available:
            response = _send_runtime_message(user_input, token=token)
            if response and "message" in response:
                speace_msg = response["message"]
                last_speace_message = speace_msg
                print(f"SPEACE: {speace_msg}")
            else:
                print("SPEACE: [Errore di connessione al runtime, passo a offline]")
                runtime_available = False
                response = dialogue_offline.receive(user_input)
                speace_msg = response["message"]
                last_speace_message = speace_msg
                print(f"SPEACE: {speace_msg}")
        else:
            response = dialogue_offline.receive(user_input)
            speace_msg = response["message"]
            last_speace_message = speace_msg
            print(f"SPEACE: {speace_msg}")

        if voice_enabled and last_speace_message:
            _speak_text(last_speace_message, speech)

    print("-" * 60)
    print("Sessione terminata.")


if __name__ == "__main__":
    main()
