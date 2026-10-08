# Verifica in casa — la lista della 0.6.0

Il motore delle regole funziona nei test, e i test non guardano una casa vera. Nella `0.5.0` sono venuti fuori tre
difetti della stessa forma, tutti in funzioni spedite e mai eseguite; la `0.6.0` aggiunge agenti, conferme e notifiche,
quindi lo stesso rischio, moltiplicato. Questa è la lista delle prove da fare **in casa**, da chi ci vive, con l'esito
scritto accanto ([#195](backlog/v0.6.0/195-verifica-in-casa.md)).

**Regola della lista:** una voce è «verificata» solo se esiste una riga del registro che la prova. Se ti sembra che
abbia funzionato ma il registro non dice niente, la voce è **da capire**, non verificata.

**Come si legge il registro.** La dashboard non lo mostra: si legge dal server.

```bash
sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/registro.py --ore 1
```

Con `--azione regola` o `--azione conferma` si guarda solo quel tipo. Le voci escono dalla più vecchia alla più recente.

**Come si compila.** Per ogni prova scrivi nelle tre righe finali: **Esito** (✅ verificata, ⚠️ funziona in parte, ❌ non
funziona, ➖ non applicabile), **Cosa ho visto**, **Riga del registro** (incollala). Ogni difetto trovato diventa una issue,
con un test che l'avrebbe trovato.

Prima di cominciare, due cose: **Home Assistant e il modello rispondono** (il Cervello dice almeno 4/5), e per le prove 1–3
serve **un dispositivo innocuo** (una lampada o una presa) che puoi accendere e spegnere senza pensarci.

---

## 1. Una regola a un orario

**Cosa fare.** Automazioni e routine → «Alle 23, spegni tutto». Scegli *A un orario* con l'ora di **tra tre minuti**,
*Accendi o spegni un dispositivo* con la lampada, e crea. La scheda deve dire quando scatterà.

**Cosa aspettarti.** Alle ore indicate la lampada cambia stato; la scheda dice «ultima: riuscita»; nel registro c'è una
voce `regola.eseguita` con esito `ok`.

```bash
sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/registro.py --azione regola --ore 1
```

- Esito: ✅ verificata (2026-10-07)
- Cosa ho visto: creata alle 21:26 dalla scorciatoia *A un orario*, programmata dallo scheduler per le 21:30:00; alle 21:30:00 ha eseguito l'azione (una routine: spegne la presa, aspetta 15 secondi, la riaccende) e alle 21:30:15 ha finito; si è riprogrammata da sola per il giorno dopo.
- Riga del registro: `regola.eseguita  ok  attore=alessio canale=web  {"regola":"reg_gfe0ad457d444a686","nome":"Nuova Routine, ogni giorno alle 21:30","motivo":"orario","azioni":[{"tipo":"modalita","riuscita":true}]}` (riportata con l'ora in UTC: lo script allora mostrava 19:30:15, vedi la correzione di `registro.py`).

## 2. Una regola su un evento (un timer)

**Cosa fare.** Nuova automazione: *Quando succede qualcosa in casa* con l'evento `timer.scaduto`, *Mandami un avviso*
(o la lampada). Poi dalla chat: «metti un timer di un minuto».

**Cosa aspettarti.** Dopo un minuto il timer suona **e** la regola scatta: avviso al telefono (o la lampada), voce
`regola.eseguita` nel registro.

- Esito: ❌ la prima volta (2026-10-07); corretto, **da riprovare dopo l'aggiornamento**
- Cosa ho visto: la regola su `timer.scaduto` è stata accettata e salvata; il timer è scaduto (21:37:48, «Timer scaduto» nel log) e **non è partito niente**: nessuna `regola.eseguita` nel registro. Causa: il motore non ascoltava `timer.scaduto` (né `promemoria.scaduto`), e la scorciatoia accettava lo stesso un evento che nessuno ascoltava. Ora il motore li ascolta e la creazione rifiuta gli eventi sconosciuti, dicendo quali si possono usare.
- Riga del registro: nessuna (è il difetto)

## 3. Una regola sul sole

Aspettare il tramonto non serve: si verifica che **il momento calcolato sia quello vero**.

**Cosa fare.** Nuova automazione *Al tramonto* con la lampada. Guarda cosa dice la scheda come «prossima volta» e
confrontalo con l'ora del tramonto di oggi nella tua città (qualunque sito meteo).

**Cosa aspettarti.** I due orari non differiscono di più di qualche minuto. Se la scheda dice «prossima: mai», la regola
è scritta male o il sole non arriva da Home Assistant: è un guasto da annotare, non una regola che aspetta.

- Esito: ✅ per il calcolo (2026-10-07); ⏳ lo scatto vero non è ancora stato osservato
- Cosa ho visto (orario nella scheda / orario vero): l'orario mostrato dalla scheda coincide con il tramonto di oggi (confronto fatto da chi vive qui).
- Riga del registro: **non ancora scattata**: nel registro non c'è nessuna `regola.eseguita` per una regola del sole. Il criterio «nessuna voce è verificata senza una riga del registro» vale per lo scatto, quindi questa voce si chiude la sera in cui la regola scatta.

## 4. Una regola che non scatta, e dice perché *(se ne hai una con una condizione)*

Se nell'editor a blocchi hai una regola con una **condizione** (per esempio «solo di sera» o «solo a casa vuota»), falla
scattare quando la condizione è falsa: il pulsante di **prova** della regola la fa girare adesso. Se non hai nessuna regola
con una condizione, scrivi ➖ e passa oltre.

**Cosa aspettarti.** L'azione non parte, e il registro dice **perché**: una voce `regola.saltata` con il motivo. È l'unico
modo per distinguere una regola che non doveva scattare da una che non è scattata per un guasto.

```bash
sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/registro.py --azione regola.saltata --ore 1
```

- Esito: ➖ non applicabile (saltata su richiesta, 2026-10-07): è facoltativa e non c'è una regola con una condizione.
- Cosa ho visto:
- Riga del registro:

## 5. La conferma di un'azione sensibile

È la prova che chiude la parte sicurezza della `0.6.0`: nessun percorso apre una serratura, disinserisce l'allarme o alza
un garage sulla parola del modello. Usa la sequenza di [CONFERME.md](CONFERME.md#5-provarla-in-due-minuti), sezione 5, con
la tua serratura (o il garage, o l'allarme).

**Cosa fare, nell'ordine.**
1. Chiedi di aprirla. Shinra deve fare la domanda e **non** aprire niente: controlla di persona.
2. Rispondi «no»: «Va bene, non faccio niente.»
3. Chiedi di nuovo e **non rispondere per tre minuti**; poi rispondi «sì»: Shinra dice che la conferma è scaduta (o che non
   c'è niente da confermare), e la serratura non si muove.
4. Chiedi una terza volta e rispondi «sì» entro tre minuti: ora la apre.

**Cosa aspettarti nel registro**, in quest'ordine: `conferma.richiesta`, `conferma.rifiutata`, `conferma.richiesta`,
`conferma.scaduta`, `conferma.richiesta`, `conferma.accettata`, e la voce dello strumento (`tool.comanda_serratura`)
solo dopo l'ultima.

```bash
sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/registro.py --azione conferma --ore 1
```

- Esito: ➖ **non provata in casa** (saltata su richiesta, 2026-10-07): in casa non c'è una serratura, un allarme o un garage da usare.
- Cosa ho visto: niente. Il meccanismo è provato soltanto dai test (`test_conferme.py`, `test_sensibilita.py`) e non da un caso vero. Non è lo stesso: i test non vedono cosa fa Home Assistant. Si può provare anche senza una serratura, con uno **script innocuo** di Home Assistant (gli script chiedono sempre conferma): vedi la proposta qui sotto.
- Righe del registro: nessuna.

> **Per chi vorrà provarla più avanti:** crea in Home Assistant `script.prova_conferma` (basta una notifica), dagli il nome «prova conferma» fra gli alias, e dalla chat scrivi «attiva la scena prova conferma». Deve chiedere conferma e non far partire lo script finché non rispondi «sì». Nel registro: `conferma.richiesta`, `conferma.rifiutata`/`conferma.accettata`, e `tool.activate_scene_or_routine` solo dopo il «sì».

## 6. Il piano a più passaggi

➖ **Non applicabile alla `0.6.0`**: i piani sono passati alla `0.7.0` ([#191](backlog/post-1.0.0/191-piani-a-piu-passaggi.md)).
Si verificherà lì.

---

## Dopo la lista

Quando le voci 1–5 hanno un esito (la 4 è facoltativa), si aggiorna la [roadmap](ROADMAP.md): il criterio della `0.4.0` («una regola creata
dall'interfaccia scatta da sola su un evento reale») passa da «da verificare» a «verificato» (voci 1 e 2 ✅) o a «non
raggiunto», con il motivo.
