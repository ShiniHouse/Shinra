# Roadmap — da 0.1.0 a 1.0.0

Ogni versione minor corrisponde a una fase. Ogni fase e' **rilasciabile**: al
tag il sistema deve essere installabile da zero, avviabile e utilizzabile.
Nessuna fase inizia prima che la precedente sia taggata.

Il principio che ordina le fasi: **quasi tutto cio' che manca dipende da due
pezzi di infrastruttura che oggi non esistono — uno scheduler e un database.**
Costruire funzioni prima di quelli significa riscriverle dopo.

---

## v0.1.0 — Impianto chiuso

> Nessuna funzione nuova. Solo cio' che oggi va in errore certo o e' pericoloso.

**Perche' per prima.** Due funzioni non hanno mai potuto funzionare, e
trentotto endpoint su trentanove accettano comandi senza autenticazione. Finche'
questo e' vero, ogni funzione nuova nasce sopra una superficie di attacco aperta.

| # | Lavoro | Riferimento |
| :-- | :--- | :--- |
| 01 | `DataStore.add_knowledge_item()` mancante | BLK-01 |
| 02 | `OllamaClient.generate()` mancante | BLK-02 |
| 03 | Autenticazione come dipendenza su tutto il router | SEC-01 |
| 04 | Verifica firma Alexa e `applicationId` | SEC-02 |
| 05 | Blocco della dashboard lato server | SEC-03 |
| 06 | PIN con hash, login corretto, rate limit su proxy | SEC-04 |
| 07 | Segreti fuori da git e in variabili d'ambiente | SEC-05 |
| 08 | `debug: false`, header di sicurezza, CORS | SEC-06 |
| 09 | Client Home Assistant unico e dinamico | REL-04 |
| 10 | Test di regressione sui difetti bloccanti | — |

**Criteri di uscita**
- I test di regressione dei due bloccanti passano senza marcatore `xfail`.
- Una richiesta non autenticata a `/api/modes/{nome}/activate` risponde `401`.
- Una POST su `/api/alexa` senza firma valida risponde `400`.
- `git ls-files` non elenca `config/config.yaml` ne' alcun file con dati personali.
- CI verde su lint, formattazione e test.

---

## v0.2.0 — Fondamenta

> I due pezzi mancanti, piu' la rete di sicurezza che permette di modificare il
> codice senza paura.

**Perche' adesso.** Timer, promemoria, automazioni, storico, spiegabilita' e sei
delle sette funzioni complementari poggiano tutte su scheduler e database.
Sono un investimento unico che sblocca l'intero resto della roadmap.

| # | Lavoro | Sblocca |
| :-- | :--- | :--- |
| 11 | Scheduler persistente (APScheduler con job store) | REL-01, REL-02, tutte le automazioni |
| 12 | SQLite + SQLAlchemy al posto dei file JSON, con migrazione | Storico, transazioni, diario |
| 13 | Memoria di conversazione per sessione | REL-03, multiutente reale |
| 14 | Configurazione in cache con invalidazione al salvataggio | REL-06 |
| 15 | Registro delle azioni (chi, cosa, quando, da quale canale) | Sicurezza, spiegabilita' |
| 16 | Layout `src/shinra/` e pacchetto installabile | Aggiunta pulita di moduli |
| 17 | Intent router estratto da `process_user_input` | Testabilita', nuovi intent |
| 18 | Suite di test, copertura ≥ 60%, pre-commit | Tutto il resto |

**Criteri di uscita**
- Un promemoria impostato a voce suona a server riavviato e senza browser aperto.
- Un timer scaduto viene marcato completato e non riappare.
- Due utenti in due schede diverse non condividono il contesto.
- `pytest --cov` riporta almeno il 60%.
- Uno script di migrazione porta i JSON esistenti nel database senza perdita.

---

## v0.3.0 — Copertura

> Riempire la matrice dei domini. A questo punto ogni voce e' un modulo nuovo,
> non un'impresa architetturale.

| # | Lavoro |
| :-- | :--- |
| 19 | WebSocket Home Assistant: stato in tempo reale ed **eventi** |
| 20 | Tool `lock`, `media_player`, `vacuum`, `fan` |
| 21 | Clima esteso (modalita', ventola, umidita') e tapparelle con posizione |
| 22 | Presenza e geofencing su `person` |
| 23 | Sicurezza domestica: allarme, aperture, notifica intrusione |
| 24 | Energia con fasce orarie italiane F1/F2/F3 |
| 25 | Liste condivise, calendario, scadenze di manutenzione |
| 26 | Collegare la configurazione fantasma (fonti RSS, categorie per profilo, argomenti vietati) |

**Criteri di uscita**
- Ogni dominio elencato come controllabile nell'interfaccia ha un tool che lo comanda.
- Nessuna impostazione esposta nell'interfaccia e' priva di un consumatore nel codice.
- Un evento Home Assistant (porta aperta) e' osservabile dall'applicazione.

---

## v0.4.0 — Proattivita'

> Shinra smette di aspettare la domanda. E' qui che si chiude anche la promessa
> sulla privacy.

| # | Lavoro |
| :-- | :--- |
| 27 | Motore di regole con trigger su evento, stato e orario |
| 28 | Nodi condizione e trigger temporale nell'editor a grafo |
| 29 | Notifiche web push (VAPID, handler `push` nel service worker) |
| 30 | Wake word locale (openWakeWord) |
| 31 | Riconoscimento vocale locale (faster-whisper) al posto della Web Speech API |
| 32 | RAG con embedding sulla knowledge base |
| 33 | Satelliti vocali per stanza |

**Criteri di uscita**
- Nessun audio della casa lascia la rete locale.
- Una regola creata dall'interfaccia scatta da sola su un evento reale.
- Il contesto inviato al modello non cresce linearmente con la knowledge base.

---

## v0.5.0 — Prodotto

> Quello che serve perche' lo installi qualcuno che non sei tu.

| # | Lavoro |
| :-- | :--- |
| 34 | Scomporre `index.html` (4.657 righe) in moduli ES |
| 35 | Backup e restore della configurazione, con versione di schema |
| 36 | Internazionalizzazione (stringhe ed espressioni regolari di intent) |
| 37 | Immagine Docker e add-on per Home Assistant OS |
| 38 | Documentazione utente e guida all'installazione verificata |

---

## v1.0.0 — Stabile

Criteri di uscita, tutti obbligatori:

1. Nessun difetto aperto di gravita' critica o alta.
2. Copertura dei test ≥ 70% su `core/` e `server/`.
3. Installazione da zero eseguita e verificata su una macchina pulita seguendo
   solo la documentazione.
4. Trenta giorni di esercizio reale senza regressioni.
5. Nessuna impostazione esposta senza un consumatore nel codice.
6. `SECURITY.md` senza difetti noti non risolti.
7. Changelog completo dalla `0.1.0`.

---

## Dopo la 1.0.0 — funzioni complementari

Sette direzioni in cui un hub locale e italiano con un LLM a bordo ha un
vantaggio strutturale. **Nessuna inizia prima della `1.0.0`**, e ognuna
poggia su infrastruttura costruita nelle fasi precedenti.

| Funzione | Dipende da |
| :--- | :--- |
| Consulente energetico a fasce F1/F2/F3 | v0.3.0 (energia) |
| Modalita' presenza e check-in per anziani | v0.3.0 (presenza) + v0.4.0 (push) |
| Registro di casa (scadenze, garanzie, contatori) | v0.2.0 (database) |
| Briefing personale per profilo | v0.2.0 (scheduler) + v0.3.0 (config collegata) |
| Spiegabilita': «perche' l'hai fatto?» | v0.2.0 (registro azioni) |
| Cucina come contesto (ricette, timer, lista) | v0.2.0 (scheduler) + v0.3.0 (liste) |
| Diario della casa | v0.2.0 (database) + v0.3.0 (eventi) |
