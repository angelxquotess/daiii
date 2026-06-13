# QUASI / MARK XXXIX-OR — Patch fix

Modifiche applicate rispetto al repo originale
(`github.com/angelxquotess/quasi`).

## 1) Nuovo comando "Invia un messaggio" + dashboard cross-platform

Quando dici a QUASI **"manda un messaggio"** (senza specificare a chi /
dove), o quando il modello chiama il tool `send_message` con
`receiver` vuoto / `platform="dashboard"`, si apre una **finestra
dedicata** che permette di:

1. Selezionare **una o piu' piattaforme** in parallelo:
   - WhatsApp
   - Telegram
   - Discord
   - Instagram
2. Cliccare **"Scansiona chat"**: per ogni piattaforma scelta viene
   eseguita una **scansione COMPLETA** delle chat e mostrata una
   **lista con selezione multipla**.
3. Scrivere il testo del messaggio.
4. Premere **INVIA** — il messaggio viene mandato a tutti i
   destinatari selezionati su tutte le piattaforme scelte.

### Come funziona la scansione

| Piattaforma | Metodo | Setup richiesto |
|---|---|---|
| WhatsApp  | HTTP GET su `http://127.0.0.1:8765/chats` (whatsapp-web.js bridge) | Vedi `WHATSAPP_OPENWA.md` |
| Telegram  | Telethon (`TelegramClient.iter_dialogs`) | Env `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` |
| Discord   | API REST `/users/@me/channels` + `/users/@me/guilds` | Env `DISCORD_USER_TOKEN` (token dell'account) |
| Instagram | instagrapi `direct_threads()` | Sessione loggata in `~/.jarvis_ig.json` |

Se la scansione di una piattaforma non trova nulla (manca il setup), in
GUI compare comunque la possibilita' di inserire manualmente il
destinatario, in CLI viene chiesto via input.

> Nessuna API a pagamento. Tutto locale.

File modificati / aggiunti:
- `actions/send_dashboard.py` — **nuovo**, contiene GUI (PyQt6) + CLI fallback.
- `actions/send_message.py`   — apre la dashboard se manca il destinatario.
- `main.py`                   — schema tool `send_message` aggiornato:
  i parametri ora sono **opzionali**, in modo che il modello possa
  invocare il tool senza specificare destinatario, lasciando la scelta
  all'utente nella dashboard.

## 2) Ottimizzazione CPU (senza modificare cosa fa)

Solo gli **intervalli di polling/animazione** sono stati alzati a
valori piu' ragionevoli: la logica e le feature sono identiche.

| Punto | Prima | Dopo | Effetto |
|---|---|---|---|
| `main.py` mic idle loop | `asyncio.sleep(0.1)` | `0.5s` | -80% wake del task asyncio |
| `ui.py` face animation timer | `16ms` (60fps) | `33ms` (30fps) | -50% redraw GPU/CPU |
| `ui.py` typewriter timer | `6ms` (~166fps) | `25ms` (40fps) | -75% pittura testo |
| `ui.py` metric timer | `2s` | `5s` | -60% campionamenti psutil |
| `ui.py` WhatsApp notify poll | `8s` | `15s` | -50% JS eval su webview |
| `actions/whatsapp_bridge.py` poll | `4s` | `8s` | -50% richieste HTTP |
| `start_quasi*.bat` | — | `/BELOWNORMAL` | priorita' processo bassa |

Nessuna feature e' stata rimossa. Tutti gli scheduler restano attivi.

## 3) Modalita' headless + `.bat`

- **`main_headless.py`** — entry point senza PyQt: stessa logica di
  `main.py` (voce, tool calling, memoria), nessuna finestra. La
  dashboard messaggi parte in modalita' CLI interattiva.
- **`start_quasi.bat`** — doppio click → avvia in headless con
  priorita' `/BELOWNORMAL`. Comandi rapidi a runtime: `mute`,
  `unmute`, `dashboard`, `quit`.
- **`start_quasi_gui.bat`** — variante che avvia la GUI classica.

Entrambi i `.bat`:
- cercano `py -3` poi `python` nel PATH;
- installano le dipendenze al primo avvio (`requirements.txt` +
  marker `.deps_ok` per evitare reinstallazioni);
- avviano il processo con priorita' bassa per non saturare la CPU.
