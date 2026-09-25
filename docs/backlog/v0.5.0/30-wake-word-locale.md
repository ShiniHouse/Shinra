---
title: "feat(voce): parola di attivazione locale"
issue: 30
milestone: "v0.5.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Non esiste alcuna parola di attivazione: bisogna premere il pulsante del
microfono oppure passare da Alexa. Un assistente domestico che richiede di
toccare uno schermo perde gran parte della propria ragione d'essere.

## Perche' e' stata spostata in v0.5.0

*Deciso l'11 settembre 2026, con Alessio.*

Due criteri di accettazione di questa scheda si verificano **solo con un
microfono vero acceso per giorni**:

> I falsi positivi restano sotto una soglia accettabile in uso reale

Una soglia di sensibilita' si taglia sui falsi positivi che si contano, non
su un numero scelto perche' sembra ragionevole. Non c'e' modo di misurarli
senza che la casa ascolti davvero, e non c'e' hardware su cui farlo: l'unico
microfono disponibile e' quello del browser.

Si poteva scrivere il codice lo stesso. Non si e' fatto, e la ragione e' che
in questa stessa versione sono venuti fuori **tre difetti della stessa
forma** — l'editor a nodi che non salvava, le regole del sole mai
programmate, le regole a orario che rispondevano 500 — tutti in funzioni
spedite e mai eseguite davvero. Una parola di attivazione mai ascoltata da un
microfono sarebbe il quarto.

## Cosa fare

- [ ] Integrare openWakeWord, che gira su CPU
- [ ] Parola personalizzabile, coerente con il nome scelto per l'assistente
- [ ] Soglia di sensibilita' regolabile
- [ ] Indicatore visivo di ascolto e possibilita' di disattivare il microfono, anche fisicamente
- [ ] Nessuna registrazione persistente dell'audio; l'audio prima dell'attivazione non lascia mai il dispositivo

## Criteri di accettazione

- [ ] Pronunciare la parola di attivazione avvia l'ascolto senza toccare nulla
- [ ] I falsi positivi restano sotto una soglia accettabile in uso reale
- [ ] Lo stato del microfono e' sempre visibile
- [ ] Nessun audio viene salvato su disco

## Cosa c'e' gia', e che serve a questa scheda

La strada che l'audio percorre e' gia' costruita dalla issue #31: la
dashboard registra, manda al **proprio** server, e Whisper trascrive in
casa. Manca solo chi preme il pulsante al posto di una mano.

La issue #33 ha aggiunto il pezzo che rende utile una parola di attivazione
in piu' stanze: un punto di ascolto sa **dove si trova**, e chi sente per
primo risponde. Senza quello, tre dispositivi svegliati dalla stessa parola
avrebbero risposto tutti e tre.

## Dove gira il riconoscimento — deciso

*25 settembre 2026, con Alessio.* **Nel browser**, su un tablet o un telefono
nella stanza: i tre modelli ONNX di openWakeWord girano nella pagina con
onnxruntime-web. Il perche', le conseguenze e le alternative scartate stanno
nell'[ADR 0007](../../adr/0007-parola-di-attivazione-nel-browser.md).

La ragione che decide e' un criterio di questa scheda: «l'audio prima
dell'attivazione non lascia mai il dispositivo». Nel browser e' vero **per
costruzione**, non per promessa.

Il prezzo, che va detto: una scheda che ascolta deve restare in primo piano
con lo schermo acceso. Il modo vero di usarla e' un tablet su un supporto,
attaccato alla corrente, con la PWA installata.

## Come si misurano i falsi positivi

Il criterio «restano sotto una soglia accettabile in uso reale» sembrava
chiedere un microfono acceso per giorni prima di poter fare qualsiasi cosa.
Non e' cosi': i falsi positivi si contano su **audio registrato**, che e' il
modo in cui li contano gli autori di openWakeWord — il loro riferimento e'
**meno di 0,5 attivazioni false all'ora**, su un corpus di circa cinque ore e
mezza di voce lontana, musica e rumore.

Una misura su registrazione si **ripete**; una dal vivo no.

1. **Una sera registrata, una volta sola** — due o tre ore nella stanza vera,
   con la televisione accesa. Chi vive in casa lo sa: e' una registrazione
   deliberata per tarare, in una cartella che poi si cancella.
2. **Il conteggio a tavolino** — la registrazione passa nel modello a soglie
   diverse, e ne esce una tabella soglia -> falsi positivi all'ora.
3. **I veri positivi** — trenta o quaranta pronunce, da vicino e dall'altra
   stanza, a voce normale e bassa. Da sola, la curva dei falsi positivi
   porterebbe a una soglia altissima e a non farsi sentire mai.
4. **La conferma dal vivo, solo alla fine** — soglia gia' scelta, qualche
   giorno acceso registrando **solo** orario e punteggio.

La misura si fa nel browser e non con uno script sul computer: il suono che
conta e' quello che esce dal microfono di quel tablet, col suo guadagno
automatico e il suo ricampionamento.

**La parola conta piu' della soglia.** «Kyra» e' corta, e le parole corte sono
la prima causa di falsi positivi — i modelli gia' addestrati di openWakeWord
sono quasi tutti di due parole. Il primo giro si fa con uno di quelli: da' una
linea di base e separa due domande che altrimenti si confondono.
