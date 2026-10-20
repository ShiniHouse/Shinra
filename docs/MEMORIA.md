# La memoria di Shinra: cosa ricorda, chi la vede, come si dimentica

Questa guida è per chi abita la casa, non per chi sviluppa. Dice in chiaro cosa Shinra tiene, chi può leggerlo e come lo si
cancella. Le scelte che stanno dietro sono negli ADR [0009](adr/0009-privacy-della-memoria.md) e
[0010](adr/0010-la-conversazione-si-conserva.md).

> **Stato:** scritta da chi ha sviluppato la funzione, **non ancora collaudata da una persona della casa** (scheda #271). Se
> qualcosa non torna con quello che vedi, vale quello che vedi: segnalalo.

## Cosa ricorda

| Cosa | Dove la vedi | Per quanto |
|---|---|---|
| **Ricordi della casa** («la caldaia è in cantina») | Conoscenza › Cosa sa Shinra › *Casa* | finché non li cancelli |
| **Ricordi tuoi** («preferisco il tè verde») | Conoscenza › Cosa sa Shinra › *I miei* | finché non li cancelli |
| **Riassunti delle conversazioni** | non si vedono come elenco | 30 giorni, poi scadono da soli |
| **Cosa ha notato di notte** | Conoscenza › *Stanotte ho notato* | 14 giorni, o finché rispondi |

Di una conversazione **non si conserva il testo**: si tiene un riassunto scritto dal codice, a partire da ciò che hai chiesto e
dalle azioni davvero eseguite. Le risposte libere dell'assistente non entrano mai, perché sono la parte che il modello può
aver inventato. Per un minore si tiene solo l'argomento (le azioni), non cosa ha scritto. Gli ospiti non hanno memoria.

## Chi vede cosa

- I ricordi **della casa** li vede chi abita qui.
- I ricordi **tuoi** li vedi **solo tu**. Nemmeno chi amministra la casa può leggere i ricordi privati di un altro, e un adulto non
  vede quelli di un minore. Se provi a raggiungere un ricordo altrui per identificativo, il server risponde «non trovato».
- Le cose notate di notte (abitudini, ricordi simili) sono tue e le vedi solo tu. Fanno eccezione i **ricordi simili della casa**:
  la proposta è della casa e la vede chi può scrivere la conoscenza della casa (non un bambino, non un ospite).
- Il registro delle azioni dice **che** è successo qualcosa («ricordo cancellato», «proposta accettata»), mai **cosa**.

## Cosa fa Shinra di notte

Di notte il codice conta nel registro le azioni che ripeti alla stessa ora, e cerca tra i tuoi ricordi quelli doppi o con un numero
diverso. Poi **propone**. Non cambia niente da solo:

- una **abitudine** accettata diventa una regola **spenta**: la accendi tu, da Routine, quando vuoi. Vale per accendere e spegnere
  un dispositivo; per serrature, allarme, garage e script non si propone nulla;
- due **ricordi simili**: scegli quale tenere e l'altro viene **archiviato**, non cancellato; lo riattivi dai ricordi;
- «No, grazie» e «Lasciali così» non tornano a chiedertelo.

Il lavoro notturno **non ha strumenti**: non può accendere una luce né aprire una porta, nemmeno se un ricordo o una conversazione
contenesse un ordine (c'è un test che lo verifica a ogni modifica). Il modello, quando c'è, al più rende più leggibile un riassunto, e
solo se non aggiunge nulla.

## Come si dimentica

- **Un ricordo**: *Elimina* nella scheda. Sparisce il testo, il suo vettore di ricerca e le proposte della notte che lo citavano.
- **Tutto di te**: *Dimentica tutto di me* (chiede conferma). Cancella i tuoi ricordi privati, i tuoi riassunti, la conversazione
  ancora in memoria e le tue proposte. Quelli della casa restano.
- **Archiviare** non è cancellare: un ricordo archiviato Shinra non lo usa più, ma c'è ancora e lo riattivi.

### I backup di prima non si riscrivono

Il salvataggio automatico della configurazione (e ogni esportazione che hai fatto) è un **file**: se contiene un ricordo e poi lo
cancelli, il file che avevi già fatto **lo contiene ancora**. Shinra non riscrive i backup passati. Un backup fatto *dopo* la
cancellazione non lo contiene. Se un ricordo era sensibile, cancella anche i vecchi file di salvataggio. I riassunti delle
conversazioni e le cose notate di notte, invece, non finiscono mai nei salvataggi.

Due cose da sapere, perché oggi sono così:

- **Il salvataggio contiene anche i ricordi privati di tutti**, non solo quelli della casa. Chi ha accesso ai file di questa
  macchina (per esempio chi amministra il server) può quindi leggerli aprendo l'archivio, anche se dall'interfaccia non può.
- **Un ripristino da un backup vecchio può riportare un ricordo che avevi cancellato.** Non esiste ancora un elenco dei ricordi
  cancellati da non rimettere. Se ripristini un archivio, ricontrolla i ricordi.

## Cosa esce dalla rete di casa

- **La memoria non esce.** Ricordi, riassunti e proposte restano su questa macchina e li legge solo il modello locale (Ollama in
  casa). Un test verifica che il codice della memoria non apra connessioni verso host esterni.
- **Le notifiche**: le notifiche al telefono del browser passano dal servizio push del produttore del browser (Google, Apple,
  Mozilla), con il testo cifrato. Se non vuoi nessun terzo, c'è il canale opzionale **ntfy in casa** ([docs/ntfy.md](ntfy.md)).
- **Canali di messaggistica esterni** (Telegram e simili): **non ci sono**, per scelta (ADR 0011).

## Se qualcosa non va

- Un ricordo che non vorresti: *Elimina*, oppure *Archivia* se vuoi tenerlo da parte.
- Shinra sa una cosa sbagliata: *Correggi* sul posto (la matita nella scheda).
- Non ti fidi più di quello che sa: *Dimentica tutto di me*, poi riparti da zero.
