---
title: "feat(sicurezza): passkey al posto del PIN, e riconoscimento di chi parla"
issue: 48
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: sicurezza"]
riferimento: "ADR 0004"
---

## Contesto

Due buchi rimasti aperti per scelta, entrambi documentati in
[ADR 0004](../../adr/0004-identita-ruoli-e-permessi.md).

**Il PIN e' cio' che si puo' digitare.** Un bambino che guarda le dita di un
adulto impara il PIN in due giorni. Una passkey no: la credenziale sta nel
dispositivo e si sblocca con impronta o riconoscimento del volto. Non c'e'
niente da indovinare e nessuno puo' usare il telefono di un altro.

**Il canale vocale non sa chi parla.** Fino a qui, chiunque si rivolga a un
Echo agisce con l'identita' della sessione: i permessi della `v0.2.0` non
proteggono la voce. E' il motivo per cui `sicurezza.comanda` resta fuori dal
canale vocale.

### Correzione: il buco era piu' largo di come l'avevamo scritto

*Aggiunto il 2026-09-10, dopo averlo misurato invece che ricordato.*

La frase qui sopra e nell'ADR 0004 dice «agisce con l'identita' della
sessione». Non era vero: il canale Alexa non impostava **mai** l'attore, e
`ha_permesso(None, ...)` concede tutto perche' `None` significa «nessuna
identita' in gioco». A voce **nessun permesso e' mai stato verificato**. Due
divieti scritti a mano nelle capacita' erano l'unica cosa che reggeva.

Con lo stesso ceppo sono venuti fuori altri due difetti: `LaunchRequest`
impostava la sessione sul primo profilo dell'elenco (l'amministratore) e lo
salutava per nome a chiunque; «sono Sonia» cambiava profilo senza nessuna
prova. Dettagli e conseguenze nell'[ADR 0004](../../adr/0004-identita-ruoli-e-permessi.md#aggiornamento--il-buco-vocale-era-piu-largo-di-come-lavevamo-scritto).

## Cosa fare

- [x] WebAuthn: registrazione e accesso con passkey
- [x] Piu' passkey per utente, una per dispositivo, revocabili singolarmente
- [x] Passkey come metodo consigliato, PIN mantenuto come ricaduta
- [x] Profili vocali Alexa: leggere l'identificativo della persona dalla
      richiesta e risolverlo nel profilo Shinra corrispondente
- [x] Se la voce non e' riconosciuta, si applicano i permessi del profilo
      ospite, non quelli dell'amministratore
- [x] Togliere il cambio di profilo parlato: un'identita' che si ottiene
      dicendola rende priva di senso ogni riga scritta sui permessi vocali
- [ ] Estendere il riconoscimento ai satelliti vocali (issue #33)
- [x] Sbloccare `sicurezza.comanda` da voce **solo** con identita' riconosciuta
      e conferma esplicita

## Criteri di accettazione

- [x] Si accede con Face ID o impronta senza digitare nulla
- [x] Una passkey revocata non consente piu' l'accesso
- [x] Con i profili vocali configurati, l'assistente sa chi ha parlato e
      applica i permessi giusti
- [x] Una voce non riconosciuta non apre serrature ne' disarma l'allarme
- [x] Chi non vuole le passkey continua a usare il PIN senza perdere nulla

## Il vincolo che la scheda dava per risolto

La scheda diceva «HTTPS gia' presente». Non lo e': su
`http://192.168.1.50:8000` — il modo in cui la maggioranza delle
installazioni domestiche raggiunge la propria dashboard — **le passkey non
funzionano affatto**, e non c'e' niente da configurare per rimediare.
WebAuthn vuole un contesto sicuro *e* un nome di dominio, e un indirizzo
numerico non e' ne' l'uno ne' l'altro.

Non e' un difetto da riparare: e' la specifica. Quello che si poteva fare, ed
e' stato fatto, e' **dirlo**: dove non si puo', il pulsante non compare e al
suo posto c'e' la ragione e il rimedio. Il PIN resta, e per questo — non solo
per chi le passkey non le vuole.

## Da verificare in casa

Il codice e' provato; l'impianto vero no, e le due cose non coincidono.

### Passkey

- [ ] Raggiungere la dashboard con un **nome** e in **HTTPS**: senza, la
      sezione Passkey dice che non sono disponibili, ed e' corretto.
- [ ] Impostazioni → Passkey → Aggiungi, e confermare con impronta o volto.
- [ ] Uscire e rientrare con «Entra con una passkey», senza digitare il PIN.
- [ ] Revocarla e verificare che il pulsante non la offra piu'.
- [ ] Verificare che il PIN continui a funzionare in ogni momento.

### Voce

- [ ] Configurare i profili vocali dall'app Alexa (Impostazioni → Il tuo
      profilo → Voce). Shinra non puo' farlo al posto di nessuno: senza,
      **tutte** le voci restano sconosciute — che e' il comportamento giusto,
      ma non e' quello che si vuole tutti i giorni.
- [ ] Parlare a un Echo e verificare che la voce compaia in Impostazioni →
      Voci Riconosciute, non associata.
- [ ] Associarla al proprio profilo e riprovare ad aprire una serratura a
      voce: dovrebbe chiedere conferma e poi aprire.
- [ ] Farla provare a qualcun altro non associato: dovrebbe rifiutare
      spiegando come farsi riconoscere.
