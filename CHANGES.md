# DAJEE / Mark XXXIX-OR — Aggiornamenti WhatsApp

File modificati rispetto al repository originale
(`github.com/angelxquotess/aaaaa`). Sostituisci questi file
nella tua cartella mantenendo la stessa struttura.

## File contenuti in questo zip

```
ui.py
main.py
core/prompt.txt
CHANGES.md                (questo file)
WHATSAPP_OPENWA.md        (guida opzionale OpenWA / whatsapp-web.js)
```

## Cosa è cambiato — riassunto

1. **WhatsApp a schermo intero / minimizza** *(nuovo)*
   - `whatsapp_control` ora accetta `action="fullscreen"` e `action="minimize"`.
   - Comandi vocali (italiano):
     * *"metti whatsapp a schermo intero"* / *"massimizza whatsapp"* / *"espandi whatsapp"* → `fullscreen` (la finestrella WhatsApp riempie tutto il pannello centrale di JARVIS).
     * *"minimizza whatsapp"* / *"rimpicciolisci whatsapp"* / *"torna alla finestra"* / *"rimetti whatsapp piccolo"* → `minimize` (torna alla finestrella 460×620).
   - La geometria "windowed" viene salvata prima di passare a fullscreen, così il ripristino è identico a com'era prima.

2. **Fix invio messaggi vocale** *(bug fix)*
   - Riscritto il JS di `send_message`:
     * **Search box**: ora prova più selettori (`data-tab="3"`, `aria-label*="erca"`, `aria-label*="earch"`, `header [contenteditable][role=textbox]`) e fa retry dopo 1.2s se non lo trova al primo colpo.
     * **Click sulla chat**: invece di un solo `chat.click()`, ora invia una sequenza `pointerdown / mousedown / pointerup / mouseup / click` con coordinate reali — sblocca i click che React/Lexical rifiutava.
     * **Casella messaggio**: aggiunto `aria-placeholder*="essag"` per coprire layout WhatsApp Web più recenti, con retry.
     * **Bottone Send**: aggiunti selettori `aria-label*="nvia"`, `aria-label*="end"`, `data-icon*="send"` (case-insensitive). Anche qui sequenza pointer events invece di click semplice.
     * **Fallback Enter**: aggiunto `charCode: 13` al `keypress` per compatibilità con vecchi listener.
   - Il callback `send_message` ora riceve `(ok, raw)` invece di solo `ok`, e JARVIS logga il messaggio grezzo della query JS (es. `WA: send FAIL -> Mario [ERR: Contatto Mario non trovato.]`) — così si vede esattamente dove fallisce.

3. **Notifica messaggi in arrivo** *(bug fix + feature)*
   - Polling JS migliorato: oltre ai badge `aria-label$="unread message(s)"` e `*="non lett*"`, ora rileva anche **badge numerici puri** (`aria-label="1"`, `"2"`, `"12+"`) usati da WhatsApp Web più recente, e copre tedesco/spagnolo (`ungelesen`, `no leid*`).
   - **Toast visuale verde-WhatsApp** in basso a destra del pannello JARVIS ogni volta che arriva un nuovo messaggio (≈5 secondi). Si somma all'annuncio vocale che JARVIS faceva già via Gemini Live.
   - Il polling parte 6s dopo l'avvio e gira ogni 8s anche con la finestrella nascosta — non serve aprire WhatsApp per ricevere le notifiche.

4. **Routing comandi vocali** (`core/prompt.txt`)
   - Aggiunte le regole di mapping per `action=fullscreen` e `action=minimize` accanto a quelle esistenti.

## OpenWA / whatsapp-web.js (opzionale)

Se vuoi rendere ancora più affidabile l'invio/ricezione senza dipendere dai selettori CSS di WhatsApp Web, vedi **`WHATSAPP_OPENWA.md`** allegato. Spiega come installare un piccolo server Node.js (gratuito, locale, nessuna chiave API) che JARVIS può chiamare via HTTP. È totalmente opzionale: tutto il resto funziona già con il solo QWebEngineView.

## Come applicare

```bash
# dentro la cartella della tua repo aaaaa:
cp ui.py main.py /percorso/al/tuo/aaaaa/
cp core/prompt.txt /percorso/al/tuo/aaaaa/core/
```

Buon J.A.R.V.I.S, signore.
