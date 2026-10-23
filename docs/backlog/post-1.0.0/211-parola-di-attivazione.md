---
title: "feat(voce): la parola di attivazione nel browser (openWakeWord)"
issue: 211
milestone: "Dopo la 1.0.0"
labels: ["tipo: funzione", "area: core", "area: frontend"]
---

## Contesto

Residuo della #30. Dove gira e' deciso (ADR 0007): **nel browser**, su un
tablet o un telefono nella stanza, con i modelli ONNX di openWakeWord e
onnxruntime-web. Cosi' «l'audio prima dell'attivazione non lascia mai il
dispositivo» e' vero per costruzione. Il codice non c'e' ancora.

I criteri sui falsi positivi si misurano su audio registrato (il riferimento di
openWakeWord e' meno di 0,5 attivazioni false all'ora), non con un microfono
acceso per giorni: il metodo e' nella scheda originale.

> **In fondo alla `0.7.0` (2026-10-08).** Il primo giro con una parola gia' addestrata, e solo dopo aver sistemato il
> riconoscimento del microfono (Whisper `small` ha scritto «pardon»). Se non e' pronta, passa a dopo la `1.0.0`.

## Cosa fare

- [ ] Un modulo della dashboard che carica i tre modelli ONNX (serviti dal repository, non da un CDN) e ascolta il microfono solo a scheda in primo piano
- [ ] Quando sente la parola avvia la registrazione gia' costruita (#31): l'audio va al **proprio** server, Whisper trascrive in casa
- [ ] Indicatore di ascolto sempre visibile, interruttore per spegnere il microfono, nessuna registrazione dell'audio prima dell'attivazione
- [ ] Parola e soglia regolabili; il primo giro con un modello gia' addestrato di due parole, poi la parola scelta
- [ ] Uno strumento per misurare: un file registrato passa nel modello a soglie diverse e produce la tabella soglia -> falsi positivi all'ora
- [ ] Con piu' stanze: risponde chi ha sentito per primo (#33)

## Criteri di accettazione

- [ ] Pronunciare la parola avvia l'ascolto senza toccare niente
- [ ] Sul corpus registrato i falsi positivi restano sotto 0,5 all'ora a una soglia che riconosce almeno nove pronunce su dieci
- [ ] Lo stato del microfono e' sempre visibile, e nessun audio viene salvato su disco
- [ ] Il test dei gesti verifica che, con il microfono spento, nessun modello sia in ascolto

## Candidati da misurare, quando la scheda parte

Non si decide adesso (la scheda e' dopo la `1.0.0`): quando parte si misurano **sulle stesse registrazioni**, con un microfono di tablet a distanza, che e' il caso d'uso dell'ADR 0007.

- **openWakeWord** (la scelta dell'ADR 0007): modelli ONNX con onnxruntime-web. Riferimento: meno di 0,5 falsi allarmi all'ora.
- **Alkove Spot** (segnalato nella issue il 2026-10-22 dal suo autore, che dichiara il proprio interesse): keyword spotting nel browser (WebAssembly e AudioWorklet), pacchetto npm `alkove`, codice e pesi Apache-2.0. La parola si **digita** in italiano, senza registrazioni ne' addestramento: la «parola regolabile» di questa scheda diventerebbe un campo di testo. Numeri **dichiarati dall'autore**, su parole italiane digitate: **79% di recall a 1 falso allarme all'ora, 74% a 0,5**; cioe' **sotto il criterio di questa scheda** (nove pronunce su dieci sotto 0,5 all'ora). Pensato per un microfono vicino; un tablet a distanza **non e' stato misurato**. E' una **versione preview**.
  - Prima di adottarlo servirebbero: la misura sul nostro corpus e a distanza; la lettura del codice e dei pesi; e l'ADR 0006 (il codice servito e' quello scritto, vendorizzato a versione fissata, non preso da un CDN o da npm a ogni installazione).
