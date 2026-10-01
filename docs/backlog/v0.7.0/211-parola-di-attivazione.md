---
title: "feat(voce): la parola di attivazione nel browser (openWakeWord)"
issue: 211
milestone: "v0.7.0"
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
