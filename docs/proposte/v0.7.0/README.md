# Proposta — hardware per l'inferenza e aiutanti locali (v0.7.0)

> **Stato: accettata (2 ottobre 2026).** Lavori nuovi della `0.7.0`, nati da due domande: *quale hardware serve
> per far girare bene il modello?* e *possono dei piccoli agenti locali fare il lavoro ripetitivo al posto di Claude,
> risparmiando token?* Le schede sono le issue **#240, #241, #242** in
> [`docs/backlog/v0.7.0/`](../../backlog/v0.7.0/). Questo documento resta come ricerca e motivazione.

## 1. L'hardware

**Dove siamo.** Intel i5-8500T (6 core, 2018), 16 GB, **nessuna scheda grafica**. Il banco della `#183` ha gia'
mostrato che il prompt (circa 5000 token tra sistema e schemi degli strumenti) non entra nella finestra che il
client usa oggi (1024–2048 token). Su una CPU come questa il collo di bottiglia non e' solo quanto in fretta
il modello *scrive*, ma quanto in fretta *legge* il prompt a ogni richiesta.

**Cosa ho trovato in rete** (ricerca del 2 ottobre 2026). Le fonti sono blog di confronto e aggregatori, non
misure ufficiali: **ordini di grandezza, da verificare**. Non ho trovato una misura dell'i5-8500T in particolare.

| Soluzione | Velocita' indicata (modelli 7–8B a 4 bit) | Costo indicato | Note |
| :--- | :--- | :--- | :--- |
| **i5-8500T (oggi)** | 3–6 token/s per una CPU senza GPU, probabilmente la parte bassa | gia' in casa | Stima generica, non misurata su questa macchina |
| **Mac mini M1 16 GB** | circa 20–25 token/s su modelli 7B; con MLX fino a +56% rispetto a Ollama in un test su M1 Max | ricondizionato circa 550–610 € in Italia (comparatori e negozi) | Memoria unificata (la GPU usa quasi tutta la RAM), consumi molto bassi da fermo, silenzioso. Il modello 2020 non si vende piu' nuovo |
| **Mini PC Ryzen 7 8845HS/8745HS, 32 GB DDR5, Radeon 780M** | 10–18 token/s | 400–650 $ | 25–45 W sotto carico. Il supporto di Ollama alle GPU integrate AMD e' delicato: da provare prima |
| **Jetson Orin Nano Super** | nessun dato trovato | — | Non raccomandabile senza una misura |
| **GPU dedicata usata (per esempio 12 GB di memoria video) in un PC** | molto piu' alta | PC + scheda, consumi alti | Fuori scala per una casa che deve restare sempre accesa |

**Cosa suggerisco.**

1. **Prima di comprare, misurare.** Tu esegui il banco della `#183` sull'i5 (`banco/README.md`). Se con un modello da
   3 miliardi di parametri il banco dice «Troncati = 0» e una latenza accettabile, **non serve hardware nuovo**.
2. **Separare il cervello dalla casa.** Shinra e Home Assistant restano dove sono; il modello gira su una macchina
   dedicata raggiunta via rete (`base_url` di Ollama e' gia' configurabile). Si sostituisce solo cio' che serve, si puo'
   provare prima, e se la macchina si ferma Shinra continua: gli intenti deterministici («accendi la luce») non
   passano dal modello.
3. **Un Mac mini M1 16 GB e' una buona candidata** per questo ruolo *(ricerca di partenza: l'acquisto non e' previsto, decisione del 2026-10-06; le prove si fanno sul portatile)*: 7–8B comodi, 14B stretti con un contesto
   largo (macOS ne usa una parte). Non e' l'unica: il mini PC Ryzen costa meno ma e' piu' incerto sul software.
4. **Provarlo prima di pagarlo**: un negozio con diritto di reso, o la macchina di qualcuno, con il banco che c'e' gia'.

**Sicurezza, non negoziabile.** L'API di Ollama **non ha autenticazione**. Un server dedicato deve ascoltare solo
sulla rete locale, con il firewall aperto solo all'indirizzo della macchina di Shinra, e **mai** dietro Cloudflare ne'
con una porta aperta verso Internet. Su macOS le applicazioni grafiche non ereditano le variabili d'ambiente della
shell: `OLLAMA_HOST` si imposta con un `LaunchAgent`, non con `.zshrc`.

## 2. Gli aiutanti locali per il lavoro di sviluppo

**L'idea.** Affidare a un piccolo modello locale (Ollama) il lavoro ripetitivo, e riservare Claude a cio' che richiede
giudizio: meno token, meno attese.

**Cosa e' realistico, e cosa no.** Un modello da 3–8 miliardi di parametri **sbaglia**: non va mai creduto sulla
parola. Funziona dove il risultato si **verifica meccanicamente**, a costo quasi nullo:

| Compito | Come si verifica |
| :--- | :--- |
| Tradurre etichette e messaggi it↔en (`#206`, `#207`) | La guardia di parita' fra le lingue, e una rilettura a campione |
| Riassumere l'esito di una suite di test lunga in «cosa e' fallito e dove» | Si confronta con il codice d'uscita e l'elenco vero dei test rossi |
| Raggruppare gli errori di `ruff` o `mypy` per causa | I numeri tornano con quelli dello strumento |
| Bozza del messaggio di commit o della descrizione di una PR dal `diff` | La rilegge e la corregge una persona |
| Candidati di codice inutilizzato | Ogni candidato si conferma con una ricerca (come per la bonifica) |

Dove **non** funziona: scrivere codice di sicurezza, decidere un'architettura, qualunque cosa il cui errore non si
vede da solo.

**Onesta' sul risparmio.** I token di Claude si consumano soprattutto in output lunghi di strumenti e in file letti per
intero; gia' oggi li taglio con `grep`, `tail` e letture parziali. Il guadagno reale di un aiutante locale va
**misurato su compiti veri**, contando anche il costo di verificare il suo output. Se il guadagno e' piccolo, la scheda
lo dice e non si costruisce altro. Inoltre, su un'i5 senza GPU un aiutante sarebbe lento (qualche token al secondo):
**il suo valore dipende dall'hardware** della prima parte.

**Come si integra.** Il modo piu' semplice, senza toccare la configurazione di Claude: uno script nel repository che
usa il client di Ollama che Shinra ha gia', chiamato da riga di comando. Un server MCP locale e' possibile, ma va
registrato nelle impostazioni dell'assistente e lo decidi tu. Si parte dallo script.

## 3. Le schede

1. [#240 — Ollama su un'altra macchina della rete](../../backlog/v0.7.0/240-ollama-su-un-server-dedicato.md)
2. [#241 — Il banco di prova sull'hardware candidato](../../backlog/v0.7.0/241-banco-sull-hardware-candidato.md)
3. [#242 — Aiutanti locali per il lavoro di sviluppo](../../backlog/v0.7.0/242-aiutanti-locali-di-sviluppo.md)

Fonti della ricerca: confronti pubblicati da
[LocalAIMaster](https://localaimaster.com/blog/apple-silicon-ai-buying-guide),
[llmcheck](https://llmcheck.net/benchmarks), [SitePoint](https://www.sitepoint.com/local-llms-apple-silicon-mac-2026/),
[TerminalBytes](https://terminalbytes.com/best-mini-pc-for-local-llm-2026/),
[compute-market](https://www.compute-market.com/blog/best-mini-pc-for-llm-under-800-2026) e
[Ryan Fleck](https://ryanfleck.ca/2025/m4-mac-mini-llm-server/) (server Ollama su un Mac mini). Nessuna e' una misura sul
nostro hardware.
