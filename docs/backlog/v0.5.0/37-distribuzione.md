---
title: "feat(distribuzione): immagine Docker e add-on per Home Assistant OS"
issue: 37
milestone: "v0.5.0"
labels: ["tipo: funzione", "area: infra"]
---

## Contesto

L'unica installazione documentata e' manuale su Debian: clonazione, ambiente
virtuale, systemd, nginx, certificati. E' una barriera notevole, e la maggior
parte delle persone che userebbero Shinra ha gia' Home Assistant OS, dove un
add-on si installa con un clic.

## Cosa fare

- [x] `Dockerfile` multi-stage e immagine pubblicata su GitHub Container Registry
- [x] `docker-compose.yml` con Shinra, Ollama e i volumi persistenti
- [ ] Add-on per Home Assistant OS con `config.yaml`, ingress e scoperta automatica dell'istanza HA
- [x] Immagini multi-architettura, incluso arm64 per Raspberry Pi
- [x] Pubblicazione automatica al tag di release

## Criteri di accettazione

- [x] `docker compose up` produce un'installazione funzionante
- [ ] L'add-on si installa su Home Assistant OS e rileva l'istanza senza configurazione manuale
- [ ] L'immagine arm64 funziona su Raspberry Pi 4

## A che punto siamo

**Fatto: la strada Docker.** `Dockerfile` a due stadi, `docker-compose.yml`
con Shinra e Ollama, pubblicazione su GHCR al tag per amd64 e arm64, e un
lavoro in CI che a ogni PR costruisce l'immagine **e la prova** — parte,
risponde, crea il profilo, genera il PIN, non gira da root, scrive il database
dove il compose monta il volume.

Quel lavoro ha trovato un difetto al primo giro: `data/examples/` non entrava
nell'immagine, quindi non nasceva nessun profilo e **nessuno poteva entrare**,
con l'applicazione che rispondeva 200 e sembrava a posto.

**Aperto, e per due ragioni dichiarate: l'add-on per Home Assistant OS.**

La prima e' che non c'e' dove provarlo. L'installazione di casa e' **HA in
Docker**, che non ha il Supervisor: li' un add-on non e' solo non collaudabile,
e' proprio non installabile. Scriverlo comunque vorrebbe dire consegnare a chi
ha HA OS qualcosa che nessuno ha mai visto funzionare — e un add-on rotto fa
perdere tempo a chi ci prova, poi torna indietro come segnalazione.

La seconda e' tecnica e piu' interessante: **l'ingress non funzionerebbe**.
Home Assistant serve gli add-on sotto un percorso come
`/api/hassio_ingress/<token>/`, e la dashboard usa percorsi assoluti —
misurati: **30** riferimenti `"/static/..."` nel markup e **62**
`fetch('/api/...')` nel JavaScript. Tutti e novantadue si romperebbero.
Renderli relativi appartiene alla **#34**, insieme ai moduli ES.

La scoperta automatica dell'istanza, invece, e' gia' gratis: dentro un add-on
Home Assistant sta a `http://supervisor/core` e il Supervisor inietta il
token, e il client di Shinra prende URL e token dall'ambiente, che ha la
precedenza su tutto. Due righe nello script di avvio, zero codice.

Quindi l'ordine, quando si riprendera': prima la #34 per i percorsi relativi,
poi l'add-on con l'ingress, su una Home Assistant OS vera.

Nel frattempo anche chi ha HA OS installa Shinra con Docker: e' scritto nel
README, nella sezione «Home Assistant OS: l'add-on non c'e' ancora», invece
di lasciarlo scoprire.

### Il Raspberry Pi

L'immagine arm64 viene costruita e pubblicata. Il criterio dice «funziona su
un Pi 4», e un Pi non c'e': si prova su altro hardware arm64. Finche' quella
prova non e' fatta, **il criterio resta aperto** — costruire e funzionare sono
due cose diverse, ed e' esattamente la distinzione che la guardia
`test_il_workflow_di_pubblicazione_costruisce_le_due_architetture` **non** puo'
fare al posto di qualcuno che guarda.
