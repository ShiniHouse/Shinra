---
title: "feat(voce): riconoscimento vocale locale al posto della Web Speech API"
issue: 31
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: core", "area: sicurezza", "gravita': alta"]
---

## Contesto

Il riconoscimento vocale usa la Web Speech API del browser, che **invia l'audio
ai server di Google**.

Il README dichiara «Zero Cloud per i Dati Privati» e «100% privata». Oggi il
modello resta in casa e la sintesi vocale passa da Microsoft Edge TTS, ma
**ogni parola pronunciata all'assistente viene inviata a Google**. E' la
contraddizione piu' netta fra cio' che il progetto promette e cio' che fa.

## Cosa fare

- [x] Integrare faster-whisper lato server, con modello configurabile per bilanciare velocita' e precisione
- [x] Endpoint di trascrizione che riceve l'audio dal browser
- [x] Mantenere la Web Speech API come alternativa esplicita, disattivata per difetto e con un avviso chiaro su cosa comporta
- [x] Valutare Piper come sintesi vocale locale, per chiudere anche l'ultimo servizio esterno — *valutata e rimandata, vedi sotto*
- [x] Aggiornare il README perche' descriva esattamente cosa resta locale e cosa no

## Criteri di accettazione

- [x] Con la configurazione predefinita, nessun audio lascia la rete locale
- [ ] La latenza di trascrizione resta accettabile su CPU per frasi brevi — **da misurare sul server vero**
- [x] Le affermazioni del README corrispondono al comportamento reale

## Piper: valutata, rimandata

Edge-TTS manda a Microsoft **il testo da leggere**, non l'audio: e' l'ultimo
servizio esterno rimasto nel percorso vocale, ed e' meno grave di quello che
questa scheda chiude — esce una risposta, non la voce di chi parla. Piper lo
chiuderebbe, e vale la pena farlo, ma non qui:

- Porta un binario e un modello di voce da installare sul server, cioe' un
  secondo pezzo da scaricare in una scheda che gia' ne aggiunge uno.
- La qualita' delle voci italiane di Piper e' sensibilmente sotto quella di
  Edge-TTS, e la sintesi e' cio' che si sente tutto il giorno: peggiorarla
  senza dirlo scontenterebbe piu' di quanto la privacy guadagni.
- Chi vuole gia' oggi togliere anche quello puo' scegliere le voci del
  browser: sono locali, e sono nelle impostazioni.

Sta come scheda a se' per la `v0.5.0`, con un criterio che questa non poteva
avere: *le voci locali devono essere abbastanza buone da non farle spegnere*.

## Da verificare in casa

Il codice e' provato; il modello vero su una CPU vera no.

- [ ] Installare il motore sul server:
      `sudo -u shinra /opt/Shinra/.venv/bin/pip install "faster-whisper>=1.0"`
      e riavviare il servizio. Il primo comando parlato scarica il modello e
      puo' volerci qualche minuto.
- [ ] Misurare la latenza di una frase breve («accendi la luce della cucina»)
      con il modello `base`. Se e' troppo lenta, provare `tiny`; se sbaglia i
      nomi di casa, provare `small`. La scelta si scrive in `voce.modello`.
- [ ] Verificare che il microfono, con il servizio **senza** faster-whisper,
      dica cosa installare invece di non fare niente.
- [ ] Verificare che parlare al vuoto non faccia partire una richiesta: la
      dashboard deve rispondere «non ho sentito niente».
