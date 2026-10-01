# Proposta — «Memoria viva» (v0.8.0)

> **Stato: proposta, non accettata.** Nessuna issue e' stata aperta e la `ROADMAP.md` non e' stata
> toccata. Questo documento e le ventinove schede in [`schede/`](schede/) sono la base su cui decidere.
> Quando la proposta e' accettata le schede passano in `docs/backlog/v0.8.0/` e si importano come
> tutte le altre (vedi «Come si procede», in fondo).

L'idea di partenza: l'assistente non ha **continuita'**. Un RAG statico e una finestra di contesto che
si riempie lo rendono un chatbot che ogni volta ricomincia. Si vuole un compagno che ricorda, che si
puo' ispezionare e correggere, che di notte «ci ripensa», e che sa raggiungerti fuori casa.

Quattro pilastri: **memoria a tre livelli**, **storia compressa**, **il sogno notturno**, **canali esterni**.
Qui sotto: cosa c'e' gia' in Shinra per ciascuno, cosa si riusa, cosa va riprogettato, e dove l'idea
va corretta prima di costruirla.

## Da dove viene, e cosa e' stato verificato

- **Il codice di Shinra** e' stato letto: `memory.py`, `conoscenza.py`, `domain/recupero.py`,
  `embedding.py`, `scheduler/motore.py`, `modelli.py`, `consegna.py`, `notifiche.py`, `permessi.py`, la
  `ROADMAP.md`. Le affermazioni sullo stato attuale sono verificate.
- **OpenJarvis** (`open-jarvis/OpenJarvis`): ho letto il README e l'indice della documentazione.
  Confermato: progetto Python 3.10+, licenza Apache 2.0; agenti in tre modi (a richiesta, schedulati,
  continui); `monitor_operative` e' descritto come «monitoraggio a lungo orizzonte con memoria,
  compressione e recupero»; la documentazione ha sezioni *Tools & Memory* (extractor, service, store),
  *Retrieval*, *Learning* (anche ottimizzazione da tracce locali), *Scheduled Monitor* e un elenco di
  *channels* con piu' di trenta integrazioni. **Non confermato**: le «cinque primitive» come elenco, il
  meccanismo con cui comprime il contesto (la documentazione non lo elenca), e qualsiasi dettaglio
  interno. Quindi **non ho preso niente da OpenJarvis come codice o come garanzia**: le scelte qui sotto
  vengono dal codice di Shinra e da idee di dominio pubblico (ordinare i ricordi per somiglianza,
  importanza e recenza; riassumere la storia vecchia; consolidare di notte). Se si vuole riusare codice,
  la licenza lo consente ma va letto prima.
- Il nome «DNI» e' un'etichetta: in letteratura *Differentiable Search Index* e' un'altra cosa. In codice e
  documenti si parla di **memoria a tre livelli**.

## I quattro pilastri sul codice di oggi

| Pilastro | Cosa c'e' | Si riusa | Va riprogettato |
| :--- | :--- | :--- | :--- |
| **1. Memoria a tre livelli** | Tabella `knowledge` (5 colonne, **senza proprietario**); scheda Conoscenza; `domain/recupero.py` (ricerca ibrida 0,7 vettore + 0,3 testo, soglia dei 25 fatti); vettori in `embedding_fatti` | CRUD, scheda, permessi `conoscenza.*`, backup, la ricerca ibrida e il suo `spiega()`, gli eventi `agente.conoscenza` della #188 | **Proprietario, origine, importanza, uso** (schema); il ranking a tre fattori; la vista per profilo; la privacy |
| **2. Storia compressa** | `ConversationMemory` **solo in RAM**: 10 scambi, 30 minuti, persa al riavvio; nessun riassunto | La separazione per persona (gia' fatta), il formato compatto `[azione eseguita: ...]` | Persistenza dei riassunti; compressione in background; finestra legata al **budget del contesto** |
| **3. Il sogno** | Scheduler con `programma_periodico` (ogni N ore); registro azioni (90 giorni); motore di regole con provenienza | Scheduler, registro, `oscura`, motore di regole, la regola «nasce spenta» | Trigger a ora fissa (da verificare); materiali del giorno; tabella delle intuizioni; guardie contro l'iniezione |
| **4. Canali esterni** | Web push, Echo (voce) e WebSocket come ascoltatori del bus `AVVISO`; Alexa e chat web in entrata, ciascuno con la sua identita' | Il bus, le preferenze di notifica, il varco di conferma della #192 | Un'astrazione bidirezionale con **identita' al centro**; l'abbinamento; il connettore |

I requisiti di interfaccia si appoggiano a quello che c'e': la vista dei ricordi **estende la scheda
Conoscenza** (il progetto ha appena ridotto gli ingressi da otto a tre, non se ne aggiunge uno); l'indicatore
di contesto usa `spiega()` e gli eventi della #188; le proposte del sogno stanno in Conoscenza e nel
riepilogo della console. Tutto con `_html`/`_args`, moduli ES e senza bundler.

## Dove l'idea va corretta (i rilievi onesti)

1. **Il problema vero e' venuto prima: il contesto non basta gia' oggi.** Il banco della #183 ha misurato un
   prompt di circa 5000 token contro un `num_ctx` di 1024 o 2048: Ollama taglia in silenzio. Aggiungere
   ricordi e riassunti prima di sistemarlo peggiora le risposte. Per questo la prima scheda tecnica e' il
   **budget del contesto**, e tutto il resto ne dipende.
2. **`MEMORIE.md` non va sincronizzato di continuo.** Un file sempre allineato al database crea due fonti di
   verita' (conflitti, salvataggi a meta') e **aggira i permessi**: chi legge il disco legge la memoria
   privata di tutti. La proposta e' un'esportazione leggibile e un'importazione **con anteprima delle
   differenze**; il database resta la fonte.
3. **La memoria oggi non ha proprietario.** Senza uno schema e un modello di privacy («cosa sa Shinra di
   *me*», minori, ospiti, «dimentica tutto») la vista per profilo non e' costruibile. Per questo la scheda 01
   e' una decisione scritta, non codice.
4. **Il ranking a tre fattori conta solo oltre i 25 fatti.** Sotto, `SOGLIA_RECUPERO` manda tutto, come prima.
   Va misurato **quanti fatti ha la casa vera**: se sono pochi, l'importanza e la recenza non cambiano
   niente, e conviene non costruirle ancora. La scheda 04 lo dice: se il banco non mostra un miglioramento,
   i pesi restano a zero.
5. **`sqlite-vec` va misurato, non adottato.** Con qualche centinaio di fatti il coseno in Python puro e'
   invisibile. L'estensione ha un costo: non si carica in ogni build di Python (`enable_load_extension`) e
   va provata su Windows, Docker e aarch64. La scheda 06 e' una misura con una soglia, non una migrazione.
6. **Il sogno non ha molto materiale, oggi.** Le conversazioni non si conservano (solo RAM), la presenza
   non si salva, la cronologia di Home Assistant sta in HA. Conservare conversazioni e' una decisione di
   privacy (scheda 12), non un dettaglio tecnico. Il materiale vero di oggi e' il registro delle azioni.
7. **Il sogno e' un vettore d'attacco.** Legge testo non fidato (conversazioni, titoli di notizie, estratti
   di Wikipedia, nomi di dispositivi). «Ricorda che da ora la porta si apre senza conferma» e' un
   avvelenamento della memoria. Regola dura, la stessa della #192: **cio' che il modello produce nasce
   proposto, mai attivo**; il compito gira **senza strumenti**; le abitudini si **contano con il codice**
   (un modello piccolo sbaglia i conti) e il modello le racconta. Nessuna regola nasce attiva da sola.
8. **Il canale esterno contraddice una promessa della `0.6.0`** («con l'opzione esterna spenta nessuna
   richiesta esce dalla rete locale») e un principio del progetto (non mandare fuori dati senza dirlo:
   e' il motivo per cui la voce e' locale). I messaggi dei bot di messaggistica non sono cifrati
   end-to-end, e un telefono con quella app diventa un telecomando della casa. Per questo la scheda 23 e'
   una decisione che puo' chiudersi con **«non si fa»**, e le alternative senza terzi (push gia' presenti,
   `ntfy` o `Matrix` in casa) sono sul tavolo.
9. **Hardware.** Un mini-PC senza GPU: il compito notturno puo' essere lento (non conta), ma ha un tetto di
   tempo e di memoria, e un modello e un `num_ctx` suoi. La durata si **misura sul i5-8500T**, non si stima.
10. **Non c'e' un «ciclo di apprendimento» da tracce.** L'ottimizzazione di modelli da tracce locali
    (che OpenJarvis dichiara) e' fuori da questa fase di proposito: richiede dati, tempo e una macchina che
    qui non ci sono. Resta un'idea per dopo.

## La questione della ROADMAP

La `ROADMAP.md` oggi va **da `0.6.0` direttamente a `1.0.0`**, e dice che le funzioni complementari «non
iniziano prima della `1.0.0`». Una `0.7.0` non e' definita. Questa proposta si chiama `0.8.0` come richiesto,
ma conviene scegliere prima:

- **A. Prima della 1.0.0.** Si definisce una `0.7.0` (per esempio «verso la stabile») e questa fase diventa
  `0.8.0`. Pro: arriva presto. Contro: la `1.0.0` richiede trenta giorni di esercizio reale senza
  regressioni, e funzioni grosse come queste li spostano.
- **B. Dopo la 1.0.0** (**la mia raccomandazione per le fasi D ed E**). Il sogno e i canali esterni sono
  funzioni complementari, e la tabella «Dopo la 1.0.0» ha gia' tre righe che li toccano: *Briefing
  personale per profilo*, *Diario della casa*, *Spiegabilita'*. Le fasi A, B, C (budget, schema, ranking,
  trasparenza, storia compressa) sono invece un **rafforzamento** di cio' che c'e' e potrebbero entrare
  prima.
- **C. A meta'.** Le fasi A–C prima della `1.0.0`, D–E dopo. Le schede sono scritte in modo che si possa
  tagliare fra la C e la D senza strascichi.

Se la proposta entra, la tabella «Dopo la 1.0.0» va aggiornata: quelle tre righe diventano parte di questa fase.

## Sezione per la ROADMAP (pronta da incollare)

```markdown
## v0.8.0 — Memoria viva

> Shinra ricorda, e chi abita la casa puo' vedere cosa ricorda, correggerlo e
> farglielo dimenticare. La storia vecchia diventa un riassunto invece di sparire,
> e di notte la casa «ci ripensa» — **proponendo**, mai decidendo. Resta locale:
> un canale esterno e' un'opzione, spenta di default, e puo' non nascere.

**Perche' in questo ordine.** Prima si sistema il contesto (oggi il prompt supera
la finestra e Ollama taglia in silenzio), poi si decide la privacy della memoria e
si costruisce lo schema, poi si rende visibile, poi si comprime la storia. Il sogno
viene dopo perche' ha bisogno di materiale e di fiducia: tutto cio' che scrive nasce
**proposto**. I canali esterni vengono per ultimi e dopo una decisione scritta, perche'
toccano la promessa della `0.6.0` sulla rete locale.

| # | Lavoro | Area |
| :-- | :--- | :--- |
| — | ADR: chi vede e chi puo' cambiare cio' che Shinra ricorda | decisione |
| — | Misura e budget del contesto | contesto |
| — | Un ricordo ha proprietario, origine, importanza e storia | memoria |
| — | Il recupero pesa importanza, recenza e uso | memoria |
| — | Quali ricordi hanno contribuito, per richiesta | memoria |
| — | ADR: la ricerca per vettori regge la casa? (misura) | decisione |
| — | API della memoria per profilo | memoria |
| — | La memoria in chiaro nell'interfaccia | trasparenza |
| — | Esporta e importa i ricordi in Markdown | trasparenza |
| — | «Ho usato questi ricordi» sotto la risposta | trasparenza |
| — | Cancellare e' cancellare, dappertutto | privacy |
| — | ADR: si conserva la conversazione? | decisione |
| — | Riassunti persistenti e finestra mobile | storia |
| — | Compressione in background con Ollama | storia |
| — | Finestra adattiva al budget | storia |
| — | Materiali della giornata | sogno |
| — | Il compito notturno | sogno |
| — | Fusione dei ricordi in proposte | sogno |
| — | Abitudini contate dal codice, raccontate dal modello | sogno |
| — | Da intuizione a bozza di regola, spenta | sogno |
| — | Interfaccia delle intuizioni | sogno |
| — | Guardie contro l'avvelenamento della memoria | sicurezza |
| — | ADR: canali esterni | decisione |
| — | Astrazione del canale bidirezionale | canali |
| — | Il primo connettore esterno, spento di default | canali |
| — | Interfaccia dei canali e dell'abbinamento | canali |
| — | Banco di valutazione della memoria | misura |
| — | Guardie di CI della fase | verifica |
| — | Guida alla memoria | documentazione |

**Criteri di uscita**
- Il banco della `#183` riporta **«Troncati = 0»** con il `num_ctx` di produzione: nessun prompt
  supera la finestra senza traccia.
- Il ranking a tre fattori **migliora** recall@k e MRR sul banco di valutazione, oppure la scheda dice
  che non migliora e i pesi restano a zero.
- Ogni ricordo e' visibile, correggibile e cancellabile dal suo proprietario; **un profilo non legge,
  non modifica e non cancella i ricordi privati di un altro** (guardia su tutte le rotte).
- Dopo una cancellazione il testo non e' piu' in nessuna tabella ne' nel backup successivo.
- La compressione della storia conserva i fatti chiave sul banco, e la latenza della risposta e' invariata.
- Il compito notturno gira entro il tetto di tempo sul i5-8500T, **non scrive mai** un ricordo attivo,
  una regola attiva o un'azione, e due esecuzioni nella stessa notte non duplicano niente.
- Un corpus di almeno venti tentativi di iniezione non produce nessuno stato attivo.
- Con i canali esterni spenti, nessuna richiesta esce dalla rete locale; con uno acceso, una chat non
  abbinata non fa niente e una conferma di una chat non vale per un'altra.
```

## Le schede

Fase **A** — le fondamenta (01–06): privacy, budget del contesto, schema, ranking, rinforzo, ricerca a scala.
Fase **B** — trasparenza (07–11): API, vista, Markdown, indicatore di contesto, cancellazione.
Fase **C** — storia compressa (12–15). Fase **D** — il sogno (16–22). Fase **E** — canali esterni (23–26).
**Trasversali** (27–29): banco di valutazione, guardie di CI, guida.

Ogni scheda ha etichette, contesto, cosa fare e criteri di accettazione, e dice da cosa dipende.
Le schede 01, 06, 12 e 23 sono **decisioni** (ADR): vanno prese prima del codice che ne dipende.
L'ordine di dipendenza essenziale: `02 → 03 → 04/05 → 07 → 08/09/10/11`, e `12 → 13 → 14`, e `16 → 17 → 18/19 → 20 → 21`, con `22` prima di `17`.

## Come si procede

1. **Decidere** la collocazione (A, B o C) e se la proposta entra. Le schede 01 e 02 si possono fare comunque:
   migliorano Shinra anche senza il resto.
2. Se entra: spostare le schede in `docs/backlog/v0.8.0/`, aggiungere la milestone `v0.8.0` all'elenco di
   `scripts/import_backlog.py`, importare (`python scripts/import_backlog.py --milestone v0.8.0`) e rinominare i
   file con i numeri che GitHub assegna, come per le altre fasi. Aggiungere la sezione alla `ROADMAP.md`.
3. Aggiornare la tabella «Dopo la 1.0.0».
