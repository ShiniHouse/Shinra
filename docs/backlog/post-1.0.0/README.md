# Dopo la 1.0.0 — funzioni complementari

Sette direzioni in cui un hub locale, italiano e con un LLM a bordo ha un
vantaggio strutturale su Alexa e Google Home.

**Nessuna di queste inizia prima del tag `v1.0.0`.** Non e' una regola formale:
ognuna poggia su infrastruttura costruita nelle fasi precedenti, e avviarla
prima significherebbe riscriverla dopo.

| Funzione | Dipende da | Perche' e' distintiva |
| :--- | :--- | :--- |
| **Consulente energetico a fasce** | v0.3.0 #24 | Nessun assistente commerciale conosce la tariffazione bioraria italiana. «Rimandare la lavastoviglie di due ore ti fa risparmiare 40 centesimi» e' una risposta che oggi nessuno da'. |
| **Modalita' presenza e check-in** | v0.3.0 #22, v0.4.0 #29 | Per un genitore anziano che vive solo: nessun movimento entro le 10, l'assistente chiede «va tutto bene?» e senza risposta avvisa un contatto. E' la funzione che trasforma un hub in qualcosa di cui una famiglia ha bisogno. |
| **Registro di casa** | v0.2.0 #12 | Scadenze e documenti che vivono su foglietti. Con un LLM a bordo si fotografa una bolletta e viene archiviata da sola. |
| **Briefing personale per profilo** | v0.2.0 #11, v0.3.0 #26 | Meteo, agenda, promemoria e notizie filtrate sul profilo, sull'altoparlante della stanza giusta all'orario giusto. |
| **Spiegabilita': «perche' l'hai fatto?»** | v0.2.0 #15 | «Perche' si e' accesa la luce del corridoio?» → «Alle 22:14 il sensore di movimento ha attivato la routine Notte». Il dato e' gia' nel registro; l'LLM sa raccontarlo. |
| **Cucina come contesto** | v0.2.0 #11, v0.3.0 #25 | Leggere i passaggi di una ricetta a voce, tre timer con nomi diversi, aggiungere alla lista cio' che manca, abbassare la musica mentre parla. |
| **Diario della casa** | v0.2.0 #12, v0.3.0 #19 | «Quanto ha funzionato il riscaldamento a gennaio rispetto a dicembre?», «A che ora rientra di solito Thomas?». E' il ritorno piu' alto dell'investimento nel database. |

## Come si aprono

Quando la `1.0.0` e' taggata, ognuna diventa una milestone `v1.1.0`, `v1.2.0` e
cosi' via, con il proprio backlog scritto allora — non adesso. Scrivere ora i
dettagli di una funzione che partira' fra mesi produce un piano che sara'
sbagliato al momento di eseguirlo.
