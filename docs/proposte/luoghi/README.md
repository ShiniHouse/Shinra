# Proposta — i luoghi, cioè più abitazioni e il «dove sei» (v0.8.0)

> **Stato: proposta (12 ottobre 2026), decisa nelle linee generali dal proprietario.** Va nella `0.8.0` insieme alla
> memoria ([#245](../memoria-viva/README.md)): il luogo è uno degli ambiti dei ricordi, accanto alle persone e alla casa.
> Le schede sono aperte: #342, #343, #344, #345 e #346 (fette a–e).

## 1. Cosa è stato chiesto

Il proprietario ha detto che Shinra **deve sapere dove si trova e quale posto è** per rispondere, e che chi gestisce la casa
può avere **più abitazioni o luoghi da registrare** oltre alla principale. Le coordinate si prendono dalla **posizione degli
smartphone o dei PC**, registrando quelle effettive: non si scrive una città a mano.

## 2. Le decisioni prese

| Domanda | Decisione |
| :--- | :--- |
| Che cos'è un'altra abitazione? | **Un solo Shinra, più luoghi.** Ogni luogo ha un nome, delle coordinate vere e una città. Più Home Assistant e uno Shinra per casa sono esclusi per ora. |
| A quale luogo si riferisce «che tempo fa?» | **A dove si trova chi parla.** Ordine: il luogo nominato nella frase («al mare», «da mia madre») vince; poi la posizione della persona; poi la casa principale. |
| Da dove arrivano le coordinate? | **Dalla posizione dello smartphone o del PC**, registrata con un gesto («registra questo luogo»), non scritta a mano. |
| Quando? | **`0.8.0`, con la memoria**, perché il luogo è un ambito dei ricordi e serve una sola migrazione dello schema. |

## 3. Cosa c'è oggi

- **Una sola città**, `assistant.default_city`, scritta a mano nella configurazione. La usano il meteo (Open-Meteo, per nome della
  città) e il prompt di sistema.
- **Alba e tramonto** vengono da Home Assistant (`sun.sun`), che ha la *sua* posizione: se un giorno ci sono due luoghi, il sole
  di uno non vale per l'altro.
- **La presenza** viene da Home Assistant: una `person` è `home` o `not_home`, e ci sono le zone. Non c'è il concetto di «sono
  al mare»: c'è «sono fuori casa».
- **L'intervista** chiede «in quale città o zona si trova la tua casa?» e salva la risposta come una frase, non come un luogo.

## 4. Come potrebbe essere fatto

**Il luogo.** Una tabella `luoghi`: identificativo, nome, tipo (abitazione, lavoro, altro), se è la principale, latitudine,
longitudine, raggio in metri (entro il quale «sei lì») e città. **Nessuna traccia degli spostamenti**: per ogni persona si tiene
solo il luogo attuale e quando è stato aggiornato.

**Registrarlo.** Due strade, entrambe con un gesto di chi è sul posto:
1. dal **telefono**, con la posizione che l'app di Home Assistant già manda (`person` e `device_tracker` hanno latitudine e
   longitudine);
2. dal **browser**, con la geolocalizzazione del browser (richiede HTTPS: c'è, dietro Cloudflare), con un pulsante
   «Registra questo luogo» nelle Impostazioni. La precisione di un PC è bassa (rete, non GPS): lo si dice in chiaro.

**Dove sei.** La posizione della persona, confrontata con i luoghi registrati: il più vicino entro il suo raggio. Fuori da tutti,
«in giro». Per i dispositivi resta la stanza o il satellite da cui si parla.

**Cosa cambia per il resto**
- il **meteo, l'alba e il tramonto** si calcolano per le coordinate del luogo giusto (Open-Meteo accetta le coordinate);
- il **prompt** dice in quale luogo si trova chi parla, non una città fissa;
- le **regole** e i **promemoria** possono dipendere da un luogo («quando arrivo al mare»), riusando le zone già lette da Home Assistant;
- i **ricordi** hanno un luogo (si aggancia a #245: proprietario, origine, importanza);
- l'**intervista** chiede «hai altre abitazioni o luoghi?» e propone di registrarli da dove sei.

## 5. La privacy, come regola

La posizione è un dato delicato, e la promessa del progetto è che resta in casa.
- Le coordinate stanno **solo sul server**; non entrano nei log, nel registro delle azioni né nel grafo.
- Si salva **il luogo attuale**, mai la traccia degli spostamenti.
- Al meteo si mandano coordinate **arrotondate a circa un chilometro**: il servizio esterno non deve conoscere l'ingresso di casa.
- La posizione di una persona la vede chi ha il permesso; ognuno può **spegnerla** e **cancellarla** dal proprio profilo.
- Un luogo registrato si può **cancellare**, e con lui le coordinate.

## 6. Le fette, in ordine

Ognuna è una PR piccola e verificabile, con una prova **su un telefono vero** (la geolocalizzazione è esattamente il tipo di
funzione che un test finto promette e un telefono smentisce: è successo con le notifiche push).

| # | Fetta | Cosa si prova |
| :-- | :--- | :--- |
| a | Il registro dei luoghi: tabella, migrazione, API, scheda nelle Impostazioni | Registrare il luogo in cui si è, dal telefono e dal browser |
| b | La posizione attuale di ogni persona e «dove sei» | Il luogo cambia da solo quando si arriva a un altro luogo registrato |
| c | Meteo, alba e tramonto per luogo, e il prompt | Lo stesso «che tempo fa?» risponde per luoghi diversi |
| d | I ricordi per luogo e le domande dell'intervista | Un fatto della casa al mare non finisce tra quelli della casa principale |
| e | Regole e promemoria per luogo | «Quando arrivo al mare» scatta all'arrivo, con una riga di registro |

## 7. Cosa resta aperto

- **Più istanze di Home Assistant.** Qui un solo Home Assistant: i dispositivi di un altro luogo non si comandano. Si riapre se serve.
- **Il fuso orario.** Si assume lo stesso per tutti i luoghi; se uno è all'estero va gestito.
- **La precisione.** Un GPS è buono, un PC no: il raggio di un luogo deve poterla assorbire, e la geolocalizzazione del browser
  va dichiarata come approssimativa.
- **Il consenso.** Ogni persona deve poter dire «non voglio essere localizzata»: da decidere se per profilo o per dispositivo.
