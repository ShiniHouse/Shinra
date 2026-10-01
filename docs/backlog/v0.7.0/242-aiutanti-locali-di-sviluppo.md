---
title: "feat(strumenti): aiutanti locali per il lavoro ripetitivo dello sviluppo, con il guadagno misurato"
issue: 242
milestone: "v0.7.0"
labels: ["tipo: funzione", "area: infra"]
---

> **Dipende da:** l'hardware della scheda 02: su una CPU senza GPU un aiutante e' lento.

## Contesto

Piccoli modelli locali (via Ollama) possono fare il lavoro ripetitivo dello sviluppo, lasciando a Claude
cio' che richiede giudizio. Il rischio e' credere a un modello che sbaglia. La regola di questa scheda: un aiutante
lavora **solo dove l'esito si verifica meccanicamente**, e il suo output e' un suggerimento, mai un fatto.

Compiti candidati: tradurre etichette e messaggi it↔en (parita' controllata dalla guardia che c'e' gia'); riassumere
una suite di test lunga in «cosa e' fallito»; raggruppare gli errori di `ruff` e `mypy`; una bozza di messaggio di
commit dal `diff`; candidati di codice inutilizzato (ognuno confermato con una ricerca).

## Cosa fare

- [ ] Uno script nel repository che usa il client di Ollama di Shinra, chiamato da riga di comando, con un sottocomando per tipo di compito
- [ ] Per ogni tipo di compito, un **controllo meccanico** dell'output prima di usarlo; un output che non passa si scarta
- [ ] Mai dentro il prompt: segreti, `.env`, dati di casa. Un elenco di cartelle e file che l'aiutante non legge
- [ ] Un piccolo banco: venti compiti per tipo, con la risposta giusta nota, e l'esito per modello
- [ ] **Misurare il guadagno vero**: token evitati, meno il costo di verificare l'output; tempo impiegato dal modello sulla macchina di casa
- [ ] Decidere per ogni tipo di compito: si usa, oppure non conviene

## Criteri di accettazione

- [ ] Ogni tipo di compito ha un esito scritto: **va** o **non va**, con i numeri
- [ ] Nessun output di un aiutante viene applicato senza il suo controllo meccanico (guardia)
- [ ] Lo script non legge i file dell'elenco escluso (test)
- [ ] Se il guadagno misurato e' trascurabile, la scheda lo dice e si chiude senza altro codice

## Come si integra

Per primo, uno script da riga di comando: non cambia la configurazione dell'assistente. Un server MCP locale e'
possibile, ma si registra nelle impostazioni dell'assistente ed e' una scelta del proprietario, da fare solo se lo
script si dimostra utile.
