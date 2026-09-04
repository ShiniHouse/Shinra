---
title: "feat(sicurezza): passkey al posto del PIN, e riconoscimento di chi parla"
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

## Cosa fare

- [ ] WebAuthn: registrazione e accesso con passkey, HTTPS gia' presente
- [ ] Piu' passkey per utente, una per dispositivo, revocabili singolarmente
- [ ] Passkey come metodo consigliato, PIN mantenuto come ricaduta
- [ ] Profili vocali Alexa: leggere l'identificativo della persona dalla
      richiesta e risolverlo nel profilo Shinra corrispondente
- [ ] Se la voce non e' riconosciuta, si applicano i permessi del profilo
      ospite, non quelli dell'amministratore
- [ ] Estendere il riconoscimento ai satelliti vocali (issue #33)
- [ ] Sbloccare `sicurezza.comanda` da voce **solo** con identita' riconosciuta
      e conferma esplicita

## Criteri di accettazione

- [ ] Si accede con Face ID o impronta senza digitare nulla
- [ ] Una passkey revocata non consente piu' l'accesso
- [ ] Con i profili vocali configurati, l'assistente sa chi ha parlato e
      applica i permessi giusti
- [ ] Una voce non riconosciuta non apre serrature ne' disarma l'allarme
- [ ] Chi non vuole le passkey continua a usare il PIN senza perdere nulla
