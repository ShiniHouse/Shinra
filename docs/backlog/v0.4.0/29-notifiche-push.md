---
title: "feat(notifiche): web push verso la PWA"
issue: 29
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: frontend", "area: infra"]
---

## Contesto

`web/static/sw.js` esiste e gestisce installazione, attivazione e cache, ma
**non ha alcun handler per l'evento `push`**. Il sistema non puo' raggiungere
l'utente quando l'applicazione non e' aperta: promemoria, allarmi, avvisi
energetici e check-in restano tutti muti.

## Cosa fare

- [x] Generazione delle chiavi VAPID e gestione delle sottoscrizioni per utente
      e dispositivo. Le chiavi si generano una volta e **non si rigenerano mai da
      sole**: cambiarle invalida in silenzio tutte le sottoscrizioni, e una casa
      che smette di avvisare senza dirlo e' peggio di una che non ha mai avvisato
- [x] Handler `push`, `notificationclick` e **`pushsubscriptionchange`** nel
      service worker. Il terzo non era chiesto ed e' il modo piu' comune in cui
      le notifiche «smettono di funzionare da sole»: il servizio push revoca una
      sottoscrizione, ne da' una nuova, e senza handler il telefono tace
- [x] Servizio di notifica unificato con instradamento per canale. **E qui si e'
      scoperto che `casa.intrusione` non arrivava da nessuna parte** — nemmeno
      alla dashboard aperta, che le note della `v0.3.0` davano per scontata
- [x] Preferenze per utente: quali categorie, quali canali, e un silenzioso
- [x] Priorita'. **Non e' un'etichetta, e' un permesso:** se il silenzioso potesse
      spegnere un allarme, sarebbe un modo per spegnere l'allarme
      dimenticandosene

## Criteri di accettazione

- [x] Un promemoria arriva sul telefono con l'applicazione chiusa
- [x] Toccare la notifica apre il punto giusto dell'applicazione, e riusa la
      finestra gia' aperta invece di aprirne una seconda
- [x] Le sottoscrizioni scadute vengono ripulite. Solo su 404 e 410, che sono il
      servizio push che dice «questo indirizzo non esiste piu'»: un timeout e'
      un'altra cosa, e togliere un telefono per un problema di rete vorrebbe dire
      smettere di avvisare qualcuno senza dirglielo
- [x] Un utente puo' silenziare una categoria senza silenziarle tutte — tranne la
      sicurezza, e il rifiuto arriva dall'API, non solo dal dominio: mostrare un
      interruttore che poi non si rispetta e' peggio che non mostrarlo

## Due cose trovate dai guardiani

**Il ratchet d'architettura** ha bocciato la prima versione delle rotte, che
importavano `infra.db` e `infra.push` direttamente: sarebbero state la
tredicesima e quattordicesima voce di `api -> infra`, il gruppo piu' numeroso
del debito. Adesso le rotte passano dal servizio, che e' anche piu' pulito.

**Il test che pretende un permesso su ogni rotta che cambia qualcosa** ha
rivelato un buco vero: `dimentica` accettava un endpoint qualunque, quindi
chiunque avesse una sessione poteva togliere il telefono di un altro
conoscendone l'indirizzo — e l'altro avrebbe smesso di ricevere gli allarmi
senza accorgersene. Le notifiche restano senza permesso, come i dispositivi
fidati e per lo stesso motivo (sono personali), ma con il controllo di
proprieta' dentro alle rotte.

## Sulla privacy, perche' «push» suona peggio di com'e'

Il browser si registra presso il **suo** servizio push — Google per Chrome,
Mozilla per Firefox, Apple per Safari — e ci consegna un indirizzo e due
chiavi. Il messaggio viene cifrato **qui** con quelle chiavi: il servizio push
instrada una busta che non puo' aprire. Un promemoria di casa passa da Google
senza che Google sappia cosa dice.
