# actions/send_dashboard.py
# Dashboard universale per inviare messaggi cross-platform.
# Quando l'utente dice "invia un messaggio" si apre una finestra che
# permette di scegliere:
#   - una o piu' piattaforme (WhatsApp, Telegram, Discord, Instagram)
#   - per ognuna fa la scansione COMPLETA delle chat e mostra la lista
#     con selezione multipla
#   - il testo del messaggio
#
# La dashboard non sostituisce nulla: e' aggiuntiva al flusso esistente.
# Funziona sia in modalita' GUI (PyQt6) sia in modalita' headless
# (console interattiva). Non blocca il thread principale: il dispatch
# avviene in un QThread/threading.

from __future__ import annotations
import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Callable, Iterable

# Platforms supportate (chiave = id interno).
PLATFORMS = ["whatsapp", "telegram", "discord", "instagram"]
PLATFORM_LABEL = {
    "whatsapp":  "WhatsApp",
    "telegram":  "Telegram",
    "discord":   "Discord",
    "instagram": "Instagram",
}


# ---------------------------------------------------------------------------
# Scansione chat (best-effort, locale, nessuna API a pagamento)
# ---------------------------------------------------------------------------

def _scan_whatsapp_chats() -> list[str]:
    """Legge i nomi delle chat WhatsApp dal bridge whatsapp-web.js
    se attivo (http://127.0.0.1:8765). Fallback: ritorna []."""
    try:
        import requests
        r = requests.get("http://127.0.0.1:8765/chats", timeout=4)
        data = r.json() if r.ok else {}
        chats = data.get("chats") or []
        return [c if isinstance(c, str) else c.get("name", "") for c in chats if c]
    except Exception:
        return []


def _scan_telegram_chats() -> list[str]:
    """Telethon (richiede TELEGRAM_API_ID/HASH + sessione gia' loggata).
    Fallback: prova a leggere ~/.telegram_session_cache.json se presente."""
    try:
        cache = Path.home() / ".telegram_session_cache.json"
        if cache.is_file():
            import json
            data = json.loads(cache.read_text(encoding="utf-8"))
            names = data.get("chats") or []
            if names:
                return list(names)
    except Exception:
        pass
    try:
        api_id   = os.environ.get("TELEGRAM_API_ID")
        api_hash = os.environ.get("TELEGRAM_API_HASH")
        if not (api_id and api_hash):
            return []
        from telethon.sync import TelegramClient
        client = TelegramClient(str(Path.home() / ".jarvis_tg"), int(api_id), api_hash)
        client.connect()
        if not client.is_user_authorized():
            client.disconnect()
            return []
        names = []
        for d in client.iter_dialogs(limit=500):
            n = getattr(d, "name", None) or getattr(d, "title", "")
            if n:
                names.append(n)
        client.disconnect()
        return names
    except Exception:
        return []


def _scan_discord_chats() -> list[str]:
    """Discord: richiede DISCORD_USER_TOKEN nell'env (token del proprio
    account). Scansione di DM e canali tramite REST."""
    try:
        import requests
        tok = os.environ.get("DISCORD_USER_TOKEN")
        if not tok:
            return []
        headers = {"Authorization": tok}
        names = []
        try:
            r = requests.get("https://discord.com/api/v9/users/@me/channels",
                             headers=headers, timeout=8)
            if r.ok:
                for ch in r.json():
                    if ch.get("type") == 1:   # DM
                        u = (ch.get("recipients") or [{}])[0]
                        names.append("DM: " + (u.get("global_name")
                                               or u.get("username") or ""))
                    elif ch.get("type") == 3: # group DM
                        names.append("Gruppo: " + (ch.get("name") or "DM"))
        except Exception:
            pass
        try:
            r = requests.get("https://discord.com/api/v9/users/@me/guilds",
                             headers=headers, timeout=8)
            if r.ok:
                for g in r.json():
                    names.append("Server: " + (g.get("name") or ""))
        except Exception:
            pass
        return [n for n in names if n]
    except Exception:
        return []


def _scan_instagram_chats() -> list[str]:
    """instagrapi: richiede sessione gia' loggata in ~/.jarvis_ig.json"""
    try:
        sess = Path.home() / ".jarvis_ig.json"
        if not sess.is_file():
            return []
        from instagrapi import Client
        cl = Client()
        cl.load_settings(str(sess))
        threads = cl.direct_threads(amount=100)
        out = []
        for t in threads:
            users = getattr(t, "users", None) or []
            label = ", ".join((getattr(u, "username", "") for u in users)) or "(thread)"
            out.append(label)
        return out
    except Exception:
        return []


SCANNERS: dict[str, Callable[[], list[str]]] = {
    "whatsapp":  _scan_whatsapp_chats,
    "telegram":  _scan_telegram_chats,
    "discord":   _scan_discord_chats,
    "instagram": _scan_instagram_chats,
}


# ---------------------------------------------------------------------------
# Sender per ciascuna piattaforma. Riusa le funzioni gia' presenti in
# actions/send_message.py per non duplicare logica.
# ---------------------------------------------------------------------------

def _dispatch(platform: str, recipient: str, text: str) -> str:
    from actions.send_message import send_message
    return send_message(parameters={
        "receiver":     recipient,
        "message_text": text,
        "platform":     platform,
    })


def send_to_targets(targets: list[tuple[str, str]], text: str,
                    on_log: Callable[[str], None] | None = None) -> list[str]:
    """Manda `text` a una lista di (platform, recipient).
    Ritorna i log riga per riga. on_log e' opzionale per la UI."""
    out = []
    for platform, recipient in targets:
        try:
            r = _dispatch(platform, recipient, text)
        except Exception as e:
            r = f"{platform}/{recipient}: errore {e}"
        out.append(r)
        if on_log:
            try:
                on_log(r)
            except Exception:
                pass
    return out


# ---------------------------------------------------------------------------
# GUI (PyQt6). Caricata solo se disponibile; altrimenti fallback CLI.
# ---------------------------------------------------------------------------

def _gui_available() -> bool:
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


def open_dashboard_gui(initial_text: str = "",
                       parent=None,
                       on_done: Callable[[list[str]], None] | None = None) -> None:
    """Apre la dashboard PyQt. Non blocca: ritorna subito.
    Lo scan parte in QThread, l'invio in QThread. on_done(logs) viene
    chiamato al termine dell'invio."""
    from PyQt6.QtCore   import Qt, QThread, pyqtSignal
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLabel,
        QListWidget, QListWidgetItem, QTextEdit, QGroupBox, QApplication,
        QSplitter, QWidget,
    )

    app_existed = QApplication.instance() is not None
    app = QApplication.instance() or QApplication(sys.argv)

    class ScanThread(QThread):
        done = pyqtSignal(str, list)
        def __init__(self, platform: str):
            super().__init__()
            self.platform = platform
        def run(self):
            try:
                names = SCANNERS[self.platform]()
            except Exception:
                names = []
            self.done.emit(self.platform, names)

    class SendThread(QThread):
        progress = pyqtSignal(str)
        finished_all = pyqtSignal(list)
        def __init__(self, targets, text):
            super().__init__()
            self.targets, self.text = targets, text
        def run(self):
            logs = send_to_targets(self.targets, self.text,
                                   on_log=lambda s: self.progress.emit(s))
            self.finished_all.emit(logs)

    dlg = QDialog(parent)
    dlg.setWindowTitle("Invia messaggio — Dashboard")
    dlg.resize(900, 600)
    dlg.setStyleSheet("""
        QDialog { background:#0f1115; color:#e6e6e6;
                  font-family:'Segoe UI', sans-serif; font-size:13px; }
        QGroupBox { border:1px solid #2a2f3a; border-radius:8px;
                    margin-top:12px; padding:8px; }
        QGroupBox::title { color:#7fdfff; padding:0 6px; }
        QCheckBox { padding:3px; }
        QPushButton { background:#1f6feb; color:white; border:none;
                      padding:8px 14px; border-radius:6px; }
        QPushButton:hover { background:#2f7fff; }
        QPushButton:disabled { background:#2a2f3a; color:#888; }
        QListWidget, QTextEdit { background:#161a22; border:1px solid #2a2f3a;
                                 border-radius:6px; color:#e6e6e6; padding:4px; }
    """)
    main_lay = QVBoxLayout(dlg)

    # --- Riga piattaforme -------------------------------------------------
    plat_box = QGroupBox("Piattaforme (selezione multipla)")
    plat_lay = QHBoxLayout(plat_box)
    plat_checks: dict[str, QCheckBox] = {}
    for p in PLATFORMS:
        cb = QCheckBox(PLATFORM_LABEL[p])
        plat_checks[p] = cb
        plat_lay.addWidget(cb)
    plat_lay.addStretch(1)
    btn_scan = QPushButton("Scansiona chat")
    plat_lay.addWidget(btn_scan)
    main_lay.addWidget(plat_box)

    # --- Splitter: liste chat + corpo messaggio ---------------------------
    split = QSplitter(Qt.Orientation.Horizontal)
    main_lay.addWidget(split, 1)

    lists_box = QGroupBox("Destinatari (seleziona uno o piu')")
    lists_lay = QVBoxLayout(lists_box)
    chats_lists: dict[str, QListWidget] = {}
    for p in PLATFORMS:
        lbl = QLabel(PLATFORM_LABEL[p] + " — nessuna scansione")
        lbl.setStyleSheet("color:#7fdfff; padding-top:6px;")
        lw  = QListWidget()
        lw.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        lw.setVisible(False)
        lbl.setVisible(False)
        lw.setObjectName("list_" + p)
        lbl.setObjectName("lbl_"  + p)
        chats_lists[p] = lw
        lists_lay.addWidget(lbl)
        lists_lay.addWidget(lw)
    lists_lay.addStretch(1)
    split.addWidget(lists_box)

    msg_box = QGroupBox("Messaggio")
    msg_lay = QVBoxLayout(msg_box)
    msg_edit = QTextEdit()
    msg_edit.setPlainText(initial_text)
    msg_edit.setPlaceholderText("Scrivi qui il messaggio da inviare a tutti i destinatari selezionati...")
    msg_lay.addWidget(msg_edit, 1)
    log_view = QTextEdit()
    log_view.setReadOnly(True)
    log_view.setMaximumHeight(160)
    log_view.setPlaceholderText("Log invio...")
    msg_lay.addWidget(log_view)
    btn_row = QHBoxLayout()
    btn_send = QPushButton("INVIA")
    btn_cancel = QPushButton("Chiudi")
    btn_row.addStretch(1)
    btn_row.addWidget(btn_cancel)
    btn_row.addWidget(btn_send)
    msg_lay.addLayout(btn_row)
    split.addWidget(msg_box)
    split.setSizes([400, 500])

    # --- Comportamento ----------------------------------------------------
    threads: list[QThread] = []

    def on_scan():
        wanted = [p for p, cb in plat_checks.items() if cb.isChecked()]
        if not wanted:
            log_view.append("Seleziona almeno una piattaforma.")
            return
        btn_scan.setEnabled(False)
        log_view.append(f"Scansione: {', '.join(PLATFORM_LABEL[p] for p in wanted)}...")
        remaining = {len(wanted)}
        for p in wanted:
            lbl = dlg.findChild(QLabel, "lbl_" + p)
            lw  = chats_lists[p]
            lbl.setText(PLATFORM_LABEL[p] + " — scansione in corso...")
            lbl.setVisible(True)
            lw.setVisible(True)
            lw.clear()
            t = ScanThread(p)
            def _make_handler(plat):
                def _done(plat_id, names):
                    lst = chats_lists[plat_id]
                    lblw = dlg.findChild(QLabel, "lbl_" + plat_id)
                    if not names:
                        lblw.setText(PLATFORM_LABEL[plat_id] + " — nessuna chat trovata (vedi README)")
                    else:
                        lblw.setText(f"{PLATFORM_LABEL[plat_id]} — {len(names)} chat")
                        for n in names:
                            QListWidgetItem(n, lst)
                    remaining[0] -= 1
                    if remaining[0] <= 0:
                        btn_scan.setEnabled(True)
                return _done
            t.done.connect(_make_handler(p))
            t.start()
            threads.append(t)

    def on_send():
        text = msg_edit.toPlainText().strip()
        if not text:
            log_view.append("Inserisci il testo del messaggio.")
            return
        targets: list[tuple[str, str]] = []
        for p, lw in chats_lists.items():
            for it in lw.selectedItems():
                targets.append((p, it.text()))
        if not targets:
            log_view.append("Seleziona almeno un destinatario.")
            return
        btn_send.setEnabled(False)
        log_view.append(f"Invio a {len(targets)} destinatari...")
        st = SendThread(targets, text)
        st.progress.connect(lambda s: log_view.append(s))
        def _fin(logs):
            log_view.append("--- Fatto ---")
            btn_send.setEnabled(True)
            if on_done:
                try:
                    on_done(logs)
                except Exception:
                    pass
        st.finished_all.connect(_fin)
        st.start()
        threads.append(st)

    btn_scan.clicked.connect(on_scan)
    btn_send.clicked.connect(on_send)
    btn_cancel.clicked.connect(dlg.close)

    dlg.show()
    if not app_existed:
        app.exec()


# ---------------------------------------------------------------------------
# CLI fallback (per modalita' headless)
# ---------------------------------------------------------------------------

def open_dashboard_cli(initial_text: str = "") -> list[str]:
    print("\n=== QUASI: Dashboard Invio Messaggi (headless) ===\n")
    print("Piattaforme disponibili: " + ", ".join(PLATFORM_LABEL.values()))
    raw = input("Quali piattaforme? (whatsapp,telegram,discord,instagram) > ").strip()
    chosen = [p.strip().lower() for p in raw.split(",") if p.strip()]
    chosen = [p for p in chosen if p in PLATFORMS]
    if not chosen:
        print("Nessuna piattaforma valida.")
        return []

    targets: list[tuple[str, str]] = []
    for p in chosen:
        print(f"\n--- Scansione {PLATFORM_LABEL[p]}...")
        names = SCANNERS[p]()
        if not names:
            print("  (nessuna chat trovata. Inserisci manualmente, vuoto = salta)")
            r = input("  destinatario > ").strip()
            if r:
                targets.append((p, r))
            continue
        for i, n in enumerate(names, 1):
            print(f"  {i:3d}. {n}")
        picks = input(f"Indici da selezionare (es. 1,3,7) per {PLATFORM_LABEL[p]} > ").strip()
        for tok in picks.split(","):
            tok = tok.strip()
            if tok.isdigit():
                idx = int(tok) - 1
                if 0 <= idx < len(names):
                    targets.append((p, names[idx]))

    if not targets:
        print("Nessun destinatario selezionato.")
        return []
    text = initial_text or input("\nMessaggio > ").strip()
    if not text:
        print("Messaggio vuoto, annullo.")
        return []
    print(f"\nInvio a {len(targets)} destinatari...")
    return send_to_targets(targets, text, on_log=lambda s: print("  " + s))


# ---------------------------------------------------------------------------
# Entry point invocato da send_message / main.py
# ---------------------------------------------------------------------------

def open_dashboard(initial_text: str = "", prefer_gui: bool = True) -> None:
    """Apre la dashboard. Non blocca in modalita' GUI.
    Se PyQt non e' disponibile usa la CLI."""
    if prefer_gui and _gui_available():
        # La GUI deve girare nel thread principale Qt. Se gia' c'e' una
        # QApplication la apriamo direttamente; altrimenti la lanciamo su
        # un thread separato con la sua loop.
        from PyQt6.QtWidgets import QApplication
        if QApplication.instance() is not None:
            open_dashboard_gui(initial_text=initial_text)
        else:
            threading.Thread(
                target=lambda: open_dashboard_gui(initial_text=initial_text),
                daemon=True,
            ).start()
    else:
        try:
            open_dashboard_cli(initial_text=initial_text)
        except Exception:
            traceback.print_exc()
