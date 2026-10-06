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

- [x] Un corpus di 30-50 richieste reali in italiano, ciascuna con lo strumento atteso e gli argomenti attesi (luci, clima, tapparelle, timer, allarme, domande senza strumento, richieste ambigue)
- [x] Un sottoinsieme a piu' passaggi («prepara la casa per la sera»)
- [x] Uno script che esegue il corpus contro un modello Ollama a scelta e produce una tabella: modello, strumento giusto %, argomenti giusti %, cicli infiniti, secondi per risposta
- [x] Un entity_id inventato dal modello conta come errore grave, a parte
- [x] Il corpus e i risultati stanno nel repository; il banco non gira in CI (serve Ollama) ma e' ripetibile con un solo comando

## Criteri di accettazione

- [ ] ~~La tabella esiste per almeno due modelli, sull'hardware del server di casa~~ — **non perseguito** (2026-10-06): vedi sotto
- [x] La scheda dice quale modello e' il minimo per gli agenti della `0.6.0`, o dice che nessuno regge e cosa cambia nel piano: **il solo modello misurato non regge le soglie**, vedi sotto
- [x] Rieseguire il banco dopo una modifica al prompt o agli strumenti e' un comando, non una serata (`banco/README.md`; con `--agenti` misura anche il router)

## Com'e' andata, e cosa manca

**Fatto: il banco.** `banco/corpus.yaml` (57 richieste in 14 categorie, comprese le frasi
ambigue e sconosciute in cui indovinare e' sbagliato, e i tentativi di far fare al modello
cio' che non deve), `banco/mondo.yaml` (la casa finta), `scripts/banco_tool_calling.py` e
`banco/README.md` con i comandi. Riproduce il ciclo dell'agente: stesso prompt, strumenti
solo se la frase li chiama e solo al primo giro, `num_ctx` di produzione. 43 test
(`test_banco.py`) provano il banco senza Ollama: un modello perfetto prende il massimo su tutto
il corpus, un modello muto no, e il ciclo gira contro un Ollama finto.

**Il banco ha trovato due difetti nel programma prima ancora di misurare un modello:**

1. **Il prompt non ci sta nel contesto.** Il prompt di sistema (~870 token) piu' gli schemi
   dei 36 strumenti (~4200) fanno circa **5000 token**; il client usa `num_ctx` **1024**
   (2048 se `max_tokens` supera 250). Ollama taglia il contesto: il modello sceglie fra
   strumenti che non ha visto. `--prova` lo dice senza bisogno di Ollama. **Da confermare con
   le misure**: la colonna «Troncati» del banco.
2. **Gli strumenti non arrivavano al modello per meta' delle richieste.** L'agente li passa
   solo se la frase contiene una delle `parole_azione`. Con un modello perfetto, **24 richieste
   su 48** che hanno uno strumento non ne contenevano nessuna: liste, agenda, scadenze, energia,
   «metti il clima a 22», «porta la tapparella al 40»... Il modello le riceveva senza strumenti
   e non poteva che inventare la risposta. **Corretto qui**: le parole sono state allargate (it e
   en) e un test lo verifica su ogni richiesta del corpus.

**Cosa manca per chiudere la scheda, e non lo puo' fare il codice:** i criteri di accettazione
chiedono la tabella per almeno due modelli **sull'hardware di casa** (i5-8500T, 16 GB, niente
GPU) e la frase su quale modello e' il minimo. Servono le misure vere: comandi in
`banco/README.md`. La scheda resta aperta finche' i risultati non sono in `banco/risultati/`.

## Com'e' finita (2026-10-06)

**La scheda e' chiusa come non pianificata per cio' che manca.** Il banco c'e', e ha fatto il suo lavoro: ha trovato e fatto
correggere cinque difetti veri (il prompt tagliato, gli strumenti che non arrivavano al modello, la cache distrutta dall'ora,
gli alias contati male, il ripiego sul catalogo intero). Le misure sono in `banco/risultati/` con le analisi.

**Misurato un solo modello**, `qwen2.5:3b`, in sei configurazioni (contesto 1024, 2048, 4096 e 8192; catalogo intero e agenti)
su due macchine (l'i5-8500T di casa e un portatile i7-1355U). Non regge le soglie dell'ADR 0008:

| | Catalogo intero @ 8192 | Agenti @ 4096 |
| :--- | ---: | ---: |
| Strumento giusto | 72,8% | 79,8% |
| Mediana | 131 s | 28,7 s |

**Cosa cambia nel piano:** il modello locale e' il ripiego, non la strada principale. I comandi semplici di ogni giorno li
risolvono gli intenti in meno di 0,2 secondi, senza modello; gli agenti di dominio rendono il ripiego piu' corto e piu'
sicuro, ma non lo rendono veloce.

**Il secondo modello non si misura.** Servirebbe un 7B, che non sta nella memoria assegnata a Ollama sul server di casa
(6 GB, con 4,7 GB solo di pesi), e il proprietario non ha intenzione di cambiare hardware: la tabella per due modelli
bloccherebbe la tabella di marcia per un dato che non cambierebbe nessuna decisione. Se un giorno l'hardware cambia, il
banco e' pronto: un comando, un'ora.
