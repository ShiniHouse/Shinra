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
`banco/risultati/2026-10-02-i5-8500t-ANALISI.md`.

I numeri che contano:

- **In produzione il prompt viene tagliato.** Con `num_ctx` 1024, Ollama legge
  ~514 token dei 5.460 e tiene solo la coda: il modello vede soltanto gli
  ultimi strumenti del catalogo e sceglie quello giusto in **4 richieste su
  96**. Non e' un difetto del modello: non ha mai visto lo strumento giusto.
- **Allargare il contesto a 8192 non basta.** Il prompt entra, ma la lettura
  costa: 4,7–7,9 token/s in lettura e 1,4–2,3 in generazione sotto i limiti
  del servizio, con una mediana di **~127 s** per richiesta. Dopo un timeout
  Ollama resta occupato 41–74 s e fa scadere anche la richiesta seguente.
- **Quando risponde, il 3B non e' cattivo:** sceglie lo strumento giusto in
  **18 richieste su 25** a contesto 8192 (72%). Il collo di bottiglia e' il
  peso del prompt, non l'intelligenza.
- **Il prefisso in cache aiuta molto** (94 s → 13 s) ma solo se la parte
  iniziale del prompt non cambia da una richiesta all'altra.

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
token**. Questa e' una **stima**, non una misura: la verifica e' un criterio
della #190.

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

- **Un solo agente con tutti gli strumenti** (oggi). Misurato: 4/96 corrette
  col contesto di produzione, ~127 s a richiesta con quello largo. Non regge
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

- Il banco, rifatto con gli agenti di dominio, deve mostrare che il **3B
  sceglie lo strumento giusto in almeno il 90%** delle richieste con risposta,
  con il contesto di produzione **senza troncamenti**, e una mediana sotto
  **~30 s** sul servizio limitato.
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
