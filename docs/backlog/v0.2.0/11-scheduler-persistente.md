---
title: "feat(scheduler): scheduler persistente per timer, promemoria e automazioni"
milestone: "v0.2.0"
labels: ["tipo: funzione", "area: infra", "gravita': critica"]
riferimento: "REL-01, REL-02 — ADR 0003"
---

## Contesto

Non esiste alcuno scheduler lato server. Ne derivano due difetti gravi:

**REL-01 — I promemoria non suonano mai.** «Ricordami di prendere le medicine
alle 17:30» viene interpretato correttamente, scritto in `data/reminders.json`,
e l'assistente risponde «Perfetto, ti ricordero'...». Poi non succede nulla:
nessun processo rilegge quel file, e la parola `reminder` non compare in nessuna
delle 4.657 righe del frontend. Per una casa che deve supportare anziani o
terapie, e' la promessa piu' pericolosa che il sistema faccia.

**REL-02 — I timer contano solo col browser aperto.** Il conto alla rovescia
vive in `startTimerTick()` (`index.html:3380`), un `setInterval` lato client. Un
timer impostato dall'Echo in cucina, senza browser aperto, non suona. I timer
scaduti non vengono mai marcati `completed` ne' rimossi: `timers.json` cresce
all'infinito e ogni voce vecchia riappare scaduta al caricamento successivo.

E' il singolo pezzo di infrastruttura mancante che blocca timer, promemoria e
qualunque automazione futura.

## Cosa fare

- [ ] `AsyncIOScheduler` di APScheduler avviato nel `lifespan` di FastAPI
- [ ] Job store `SQLAlchemyJobStore` sul database della issue #12: i job sopravvivono al riavvio
- [ ] Alla creazione di un timer o promemoria si registra un job; alla cancellazione lo si rimuove
- [ ] Alla scadenza il job pubblica un evento interno; i canali in ascolto lo consegnano
- [ ] Consegna verso l'interfaccia web tramite WebSocket, non piu' polling
- [ ] Consegna vocale su un Echo tramite `notify.alexa_media`: **collegare finalmente `speak_on_alexa()`, oggi definita e mai chiamata, e `alexa_media_player_entity`, oggi configurabile e mai letta**
- [ ] `misfire_grace_time` per tipo di job: un promemoria di mezz'ora fa si consegna ancora, un timer della pasta no
- [ ] Marcare i timer completati e ripulirli dopo un periodo di conservazione

## Criteri di accettazione

- [ ] Un promemoria per fra due minuti suona anche riavviando il servizio nel frattempo
- [ ] Un timer impostato a voce suona senza alcun browser aperto
- [ ] Un timer scaduto risulta completato e non riappare al caricamento successivo
- [ ] Con un Echo configurato, l'annuncio arriva sull'altoparlante
- [ ] Esiste un test che verifica la ripresa dei job dopo il riavvio
