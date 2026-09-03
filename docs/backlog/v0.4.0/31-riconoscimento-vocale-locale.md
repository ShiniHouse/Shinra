---
title: "feat(voce): riconoscimento vocale locale al posto della Web Speech API"
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

- [ ] Integrare faster-whisper lato server, con modello configurabile per bilanciare velocita' e precisione
- [ ] Endpoint di trascrizione che riceve l'audio dal browser
- [ ] Mantenere la Web Speech API come alternativa esplicita, disattivata per difetto e con un avviso chiaro su cosa comporta
- [ ] Valutare Piper come sintesi vocale locale, per chiudere anche l'ultimo servizio esterno
- [ ] Aggiornare il README perche' descriva esattamente cosa resta locale e cosa no

## Criteri di accettazione

- [ ] Con la configurazione predefinita, nessun audio lascia la rete locale
- [ ] La latenza di trascrizione resta accettabile su CPU per frasi brevi
- [ ] Le affermazioni del README corrispondono al comportamento reale
