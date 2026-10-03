# 0008 — Agenti per dominio, non un modello con tutti gli strumenti

- **Stato:** Proposto
- **Data:** 2026-10-02
- **Attuazione:** milestone `v0.6.0`, issue #184 (costruzione: #190, #191)

## Contesto

Oggi il modello locale riceve **tutto il catalogo**: 36 strumenti in 8 domini,
circa **5.460 token** fra schemi e istruzioni. Il banco di prova (#183,
`banco/`) ha misurato cosa succede su un i5-8500T senza GPU, con Ollama
limitato a 3 core e priorita' bassa (`CPUQuota`, `Nice`), il servizio che
girera' davvero in casa. Le analisi complete sono in
`banco/risultati/2026-10-02-i5-8500t-ANALISI.md` (primo giro) e
`banco/risultati/2026-10-02-i5-8500t-2-ANALISI.md` (secondo giro, col banco
corretto: i numeri qui sotto vengono da quest'ultimo).

I numeri che contano:

- **In produzione il prompt viene tagliato.** Con `num_ctx` 1024, Ollama legge
  514 token dei 5.459 e tiene solo la coda: il modello vede soltanto gli
  ultimi strumenti del catalogo. Su 114 richieste lo strumento giusto esce 23
  volte, e sono quasi tutte frasi dove non c'e' niente da chiamare
  (conversazione, ambigua, sconosciuta): sui comandi di casa, clima,
  tapparelle, energia e sicurezza fa **0 su 0**. Non e' un difetto del
  modello: non ha mai visto lo strumento giusto.
- **Allargare il contesto a 8192 non basta.** Il prompt entra, ma la lettura
  costa: la mediana e' di **131 s** per richiesta, circa **42 token/s** di
  lettura sotto `CPUQuota=500%` e `Nice=5`. (Il primo giro, con 300% e la
  macchina piu' carica, dava 4,7–7,9 token/s: condizioni diverse, non
  confrontabili.)
- **Quando legge tutto, il 3B non e' cattivo:** sceglie lo strumento giusto in
  **83 richieste su 114 (72,8%)** a contesto 8192, e fra queste gli argomenti
  sono giusti 60 volte su 75 (80%, rivalutando gli alias che l'app risolve).
  Gli errori sono di scelta fra troppe opzioni: una luce comandata con lo
  strumento delle tapparelle, e una porta «chiudi a chiave» eseguita come
  **sblocca**. Le frasi ambigue danno 0/6: con il catalogo intero sceglie
  comunque uno strumento di comando.
- **Il prefisso in cache vale un fattore 10–40.** Le richieste ripetute
  subito dopo costano 3–10 s invece di 130, ma solo se la parte iniziale del
  prompt non cambia da una richiesta all'altra.

Pesi misurati degli schemi per dominio (token, circa):

| Dominio | Strumenti | Token |
| :--- | ---: | ---: |
| agenda | 11 | 989 |
| clima e tapparelle | 4 | 669 |
| dispositivi | 4 | 616 |
| casa | 4 | 552 |
| informazioni | 4 | 460 |
| sicurezza | 3 | 387 |
| energia | 3 | 275 |
| promemoria | 3 | 272 |
| **totale** | **36** | **4.223** |

Il resto dei 5.460 sono le istruzioni comuni. Un solo dominio pesa fra 275 e
989 token: con le istruzioni, un agente di dominio sta sotto i **~1.500–2.000
token**. Questa e' una **stima**, non una misura. A 42 token/s un agente da 2.000
token letto da zero costa ancora circa **48 s**: il guadagno vero viene dal
**prefisso in cache** e dalla scelta fra meno strumenti, non dal prompt corto
da solo. La verifica e' un criterio della #190.

## Decisione

**Un router sceglie il dominio, e un agente di dominio vede solo gli
strumenti di quel dominio.**

1. **Router deterministico per primo.** Parole chiave e intenti gia' noti
   (che il sistema ha gia' in `services/intenti/`) risolvono la grande
   maggioranza delle frasi senza chiamare il modello. Il modello compare solo
   per le frasi ambigue, e in quel caso vede soltanto **i nomi e una riga di
   descrizione degli 8 domini**, non gli schemi.
2. **Ogni agente dichiara i propri strumenti.** Un agente e' un elenco
   esplicito di nomi di strumenti piu' le sue istruzioni. Il prompt viene
   costruito **solo** da quell'elenco: uno strumento che non e' dichiarato non
   compare nello schema e, soprattutto, non viene **eseguito** anche se il
   modello lo inventa. Il controllo sta nell'esecuzione, non nel prompt: il
   modello non e' fidato (vedi #192).
3. **Il prefisso e' stabile.** Istruzioni e schemi del dominio vengono prima;
   cio' che cambia a ogni richiesta (data, ora, stato della casa) va in coda.
   Cosi' la cache dei prefissi di Ollama lavora a favore.
4. **Se il router sbaglia dominio**, l'agente sbagliato non ha lo strumento
   giusto. Per costruzione non puo' fare danni (non vede gli strumenti
   altrui), e puo' fare una sola cosa: dichiarare `fuori_dominio`. A quel
   punto il router riprova **una volta** col secondo dominio candidato; se
   fallisce di nuovo, Shinra dice che non ha capito invece di tirare a
   indovinare. Il numero di rimbalzi e' limitato a due.
5. **Le azioni sensibili restano sensibili.** La conferma per persona e per
   canale (#192) sta sopra gli agenti: un agente non puo' scavalcarla.

## Alternative scartate

- **Un solo agente con tutti gli strumenti** (oggi). Misurato: 0 comandi
  riusciti col contesto di produzione, 72,8% di strumenti giusti e 131 s a
  richiesta con quello largo. Non regge
  su questo hardware, e peggiora ad ogni strumento aggiunto.
- **Un agente per strumento.** 36 agenti, 36 prompt da mantenere, e un router
  che deve distinguere `crea_scadenza` da `dimentica_scadenza`: la parte
  difficile resterebbe tutta al router, e il guadagno per prompt sarebbe
  minimo rispetto a un dominio da 3–4 strumenti.
- **Un pianificatore esterno** (un modello grande in cloud sceglie gli
  strumenti). Funziona, ma manda fuori casa frasi dette in casa e le rende
  dipendenti dalla rete. Resta lecito come *opzione dichiarata dall'utente*,
  non come architettura di base. Il riuso dei piani a piu' passaggi (#191)
  e' un'altra decisione.
- **Solo allargare il contesto e aspettare un hardware piu' veloce.** Non
  risolve niente oggi e rende ogni richiesta lenta anche sul hardware
  migliore, perche' il costo cresce con il prompt.

## Conseguenze

- Prompt piu' corti: meno lettura, piu' cache, minore possibilita' di
  scegliere uno strumento sbagliato fra 36.
- Un livello in piu' da testare: il router. Si misura con lo stesso banco
  (accuratezza del dominio, poi dello strumento).
- Aggiungere uno strumento significa decidere **a quale dominio appartiene**.
  Un guard nei test controlla che ogni strumento stia in un solo agente.
- Frasi che toccano due domini («spegni tutto e dimmi il meteo») vengono
  scomposte dal router in due passaggi, non gestite da un agente con
  entrambi gli strumenti.

## La misura / cosa cambierebbe

La decisione si regge su due numeri, e ha una soglia prima di diventare
`Accettato`:

- Il banco, rifatto con gli agenti di dominio e il contesto di produzione
  **senza troncamenti**, deve mostrare: strumento giusto **≥ 85%**, argomenti
  giusti **≥ 75%**, strumenti inventati **≤ 1**, nessuna azione opposta a
  quella chiesta (serrature incluse). Sono i criteri che il banco gia'
  propone; qui diventano quelli della decisione.
- La mediana deve stare sotto **15 s con il prefisso in cache**, che e' la
  condizione di tutti i giorni dopo la prima richiesta. Da freddo, la prima
  richiesta di un agente puo' costare fino a ~50 s: va dichiarato, non
  nascosto. Il criterio di 8 s che il banco propone oggi non e' raggiungibile
  a 42 token/s nemmeno con 2.000 token da freddo, e va allineato a questo
  quando l'ADR passa ad Accettato.
- Il prompt di un agente deve pesare **meno di 2.000 token** (la stima di
  sopra, da verificare).

Cosa cambierebbe:

- Se il router deterministico sbaglia dominio in piu' del **10%** delle frasi
  reali, il costo dei rimbalzi cancella il vantaggio: si rivaluta un router
  piu' semplice (meno domini) o un modello piu' grande **solo** per il router.
- Se il giro lungo (3B e 7B a macchina libera) mostrasse che un 7B con
  catalogo intero e' veloce a sufficienza su un hardware candidato (Mac mini
  M1, scheda #241), gli agenti restano comunque utili per la precisione, ma
  l'urgenza cala: l'ADR passerebbe da necessita' a ottimizzazione.
- Se il 3B con un dominio solo restasse sotto la soglia, il problema non e'
  il catalogo ma il modello, e la strada diventa un modello diverso.
