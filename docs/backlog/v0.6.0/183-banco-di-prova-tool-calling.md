---
title: "test(agente): un banco di prova che misura quale modello sceglie lo strumento giusto"
issue: 183
milestone: "v0.6.0"
labels: ["tipo: attivita'", "area: core"]
---

## Contesto

La `0.6.0` poggia su una scommessa: che il modello locale, servito da Ollama,
scelga lo strumento giusto e gli passi gli argomenti giusti anche quando la
richiesta e' ambigua o richiede piu' passaggi. Oggi nessuno ha misurato
quanto spesso succeda. Senza il dato, gli agenti per dominio e i piani a piu'
passaggi sono una scommessa.

Per questo e' la **prima** scheda della fase: decide quanto sono ambiziose
le altre.

## Cosa fare

- [ ] Un corpus di 30-50 richieste reali in italiano, ciascuna con lo strumento atteso e gli argomenti attesi (luci, clima, tapparelle, timer, allarme, domande senza strumento, richieste ambigue)
- [ ] Un sottoinsieme a piu' passaggi («prepara la casa per la sera»)
- [ ] Uno script che esegue il corpus contro un modello Ollama a scelta e produce una tabella: modello, strumento giusto %, argomenti giusti %, cicli infiniti, secondi per risposta
- [ ] Un entity_id inventato dal modello conta come errore grave, a parte
- [ ] Il corpus e i risultati stanno nel repository; il banco non gira in CI (serve Ollama) ma e' ripetibile con un solo comando

## Criteri di accettazione

- [ ] La tabella esiste per almeno due modelli, sull'hardware del server di casa
- [ ] La scheda dice quale modello e' il minimo per gli agenti della `0.6.0`, o dice che nessuno regge e cosa cambia nel piano
- [ ] Rieseguire il banco dopo una modifica al prompt o agli strumenti e' un comando, non una serata
