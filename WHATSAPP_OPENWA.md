# Integrazione opzionale: OpenWA / whatsapp-web.js

**Quando ti serve?** Se l'iniezione JS dentro QWebEngineView fallisce
spesso (WhatsApp cambia spesso i selettori CSS), puoi usare una libreria
"vera" che parla con WhatsApp Web tramite Puppeteer + protocollo
ufficiale. Tutto **gratis** e **locale**, niente API a pagamento,
nessuna chiave segreta da chiedere.

Esistono due opzioni equivalenti, scegli quella che preferisci:

| Libreria | Repo | Linguaggio |
|---|---|---|
| **whatsapp-web.js** (più mantenuta, consigliata) | https://github.com/pedroslopez/whatsapp-web.js | Node.js |
| **OpenWA / @open-wa/wa-automate** | https://github.com/rmyndharis/OpenWA / https://github.com/open-wa/wa-automate-nodejs | Node.js |

Entrambe espongono in pratica le stesse cose:
- invio messaggi (`client.sendMessage("39333xxx@c.us", "ciao")`)
- evento `message` quando arriva un messaggio (lo intercetti via callback)
- gestione QR scan iniziale (poi la sessione viene salvata in locale)

---

## 1) Setup (whatsapp-web.js, consigliato)

```bash
# Servono Node 18+ e npm
mkdir wa-bridge && cd wa-bridge
npm init -y
npm install whatsapp-web.js express qrcode-terminal
```

Crea il file `wa-bridge/server.js`:

```js
const express   = require("express");
const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode    = require("qrcode-terminal");

const app  = express();
app.use(express.json());

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: "./wa-session" }),
  puppeteer:    { headless: true, args: ["--no-sandbox"] },
});

let lastIncoming = [];  // memoria volatile dei messaggi ricevuti

client.on("qr", qr => qrcode.generate(qr, { small: true }));
client.on("ready", () => console.log("[wa-bridge] ready"));
client.on("message", async msg => {
  const c = await msg.getContact();
  lastIncoming.push({
    from:  c.pushname || c.number,
    body:  msg.body,
    at:    Date.now(),
  });
  // Tieni solo gli ultimi 50
  if (lastIncoming.length > 50) lastIncoming.shift();
});

// --- API HTTP che JARVIS chiamerà --------------------------------------

// POST /send  { "to": "Mario Rossi", "text": "ciao" }
app.post("/send", async (req, res) => {
  try {
    const { to, text } = req.body;
    // Risoluzione del contatto: prima prova come numero, poi cerca
    // tra i contatti per nome (fuzzy: include + case-insensitive).
    let chatId = null;
    if (/^\d+$/.test(to)) {
      chatId = to.includes("@") ? to : `${to}@c.us`;
    } else {
      const contacts = await client.getContacts();
      const want = to.toLowerCase();
      const m = contacts.find(c =>
        (c.name || c.pushname || "").toLowerCase().includes(want)
      );
      if (!m) return res.status(404).json({ ok:false, err:"contact not found" });
      chatId = m.id._serialized;
    }
    await client.sendMessage(chatId, text);
    res.json({ ok: true });
  } catch (e) { res.status(500).json({ ok:false, err: String(e) }); }
});

// GET /unread  -> lista degli ultimi messaggi ricevuti
app.get("/unread", (_req, res) => {
  res.json({ ok: true, messages: lastIncoming.splice(0) });
});

client.initialize();
app.listen(8765, () => console.log("[wa-bridge] http://127.0.0.1:8765"));
```

Avvialo:

```bash
node server.js
# La prima volta scansiona il QR con il telefono (Impostazioni →
# Dispositivi collegati). La sessione viene salvata in ./wa-session
# e i restart successivi sono automatici.
```

## 2) Aggancio dentro JARVIS (lato Python)

Aggiungi in `actions/whatsapp_bridge.py` (file nuovo, opzionale):

```python
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
            time.sleep(4)
    threading.Thread(target=_loop, daemon=True).start()
```

Poi, dentro `JarvisLive.__init__` (in `main.py`), puoi avviarlo:

```python
from actions.whatsapp_bridge import start_incoming_poller, send_via_bridge
start_incoming_poller(lambda name, body:
    self.ui.write_log(f"WA(bridge): {name}: {body}"))
```

E nel branch `whatsapp_control` di `_handle_command`, se vuoi usare il
bridge come metodo PRIMARIO (con fallback alla web view JS già esistente):

```python
elif name == "whatsapp_control" and (args.get("action") == "send_message"):
    ok, raw = send_via_bridge(args.get("recipient",""), args.get("message",""))
    if ok:
        result = f"Messaggio inviato a {args.get('recipient')}, signore."
    else:
        # fallback: usa la web view dentro JARVIS
        self.ui.show_whatsapp_overlay("send_message",
            args.get("recipient",""), args.get("message",""))
        result = f"Invio messaggio WhatsApp a {args.get('recipient')}."
```

## 3) Note importanti

- **Tutto gratis**: nessuna chiave API, nessun account WhatsApp Business,
  nessun servizio cloud. Solo Node + il tuo numero WhatsApp.
- **Sessione persistente**: la cartella `wa-session` salva il login,
  non serve riscansionare il QR ad ogni avvio.
- **Limite**: WhatsApp può sospendere account che inviano spam massivo.
  Per uso personale (≤ 50 msg/giorno verso numeri reali) è sicuro.
- **Avvio automatico**: puoi far partire `node server.js` insieme a JARVIS
  con un `subprocess.Popen` in `main.py`, oppure metterlo nei programmi
  all'avvio del sistema.
- **Variante OpenWA**: tutto identico, cambia solo l'import. In `server.js`
  sostituisci con:
  ```js
  const wa = require("@open-wa/wa-automate");
  wa.create({sessionId: "JARVIS", multiDevice: true}).then(client => {
    client.onMessage(msg => { /* … */ });
    // client.sendText("Mario@c.us", "ciao")
  });
  ```
