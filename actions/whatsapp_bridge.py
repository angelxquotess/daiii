import requests, threading, time

WA_BASE = "http://127.0.0.1:8765"

def send_via_bridge(recipient: str, message: str) -> tuple[bool, str]:
    try:
        r = requests.post(f"{WA_BASE}/send",
                          json={"to": recipient, "text": message},
                          timeout=15)
        ok = r.ok and r.json().get("ok") is True
        return ok, r.text
    except Exception as e:
        return False, f"ERR: {e}"

def start_incoming_poller(on_message):
    """on_message(from_name, body) viene chiamato per ogni messaggio nuovo."""
    def _loop():
        while True:
            try:
                r = requests.get(f"{WA_BASE}/unread", timeout=8)
                for m in r.json().get("messages", []):
                    on_message(m.get("from",""), m.get("body",""))
            except Exception:
                pass
            time.sleep(8)
    threading.Thread(target=_loop, daemon=True).start()