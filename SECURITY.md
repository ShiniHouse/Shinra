# Politica di sicurezza

Shinra controlla luci, prese, clima e — nella roadmap — serrature e allarme di
un'abitazione reale. Un difetto di sicurezza qui non e' un problema di dati: e'
un problema di casa.

## Versioni supportate

| Versione | Supporto |
| :--- | :--- |
| `0.1.0` e successive | Si' |
| Precedenti alla `0.1.0` | **No.** Contengono i difetti elencati sotto. |

## Segnalare una vulnerabilita'

Non aprire una issue pubblica. Usa
[GitHub Security Advisories](https://github.com/ShiniHouse/Shinra/security/advisories/new).
Risposta entro 72 ore.

---

## Difetti noti — stato al 3 settembre 2026

Individuati da una revisione completa del codice al commit `a622043`. Sono
pubblicati perche' **chiunque stia usando il progetto prima della `0.1.0` deve
sapere a cosa e' esposto**. Tutti sono in lavorazione nella milestone `v0.1.0`.

| ID | Gravita' | Difetto | Stato |
| :--- | :--- | :--- | :--- |
| SEC-01 | Critico | Un solo endpoint su trentanove verifica l'autenticazione. `POST /api/modes/{nome}/activate` esegue una routine domotica senza credenziali. | **Risolto in v0.1.0** |
| SEC-02 | Critico | `/api/alexa` non verifica la firma Amazon ne' l'`applicationId`. Se esposto su Internet, accetta comandi da chiunque. | **Risolto in v0.1.0** |
| SEC-03 | Alto | Il blocco della dashboard e' un overlay CSS: i dati sono gia' stati inviati al browser. | Aperto |
| SEC-04 | Alto | Senza PIN configurato, qualunque PIN ottiene una sessione valida. Il rate limit usa `request.client.host`, che dietro reverse proxy e' identico per tutti. | Aperto |
| SEC-05 | Alto | `config/config.yaml` e' tracciato da git e riceve il token Home Assistant al salvataggio dalle impostazioni. | **Risolto in v0.1.0** |
| SEC-06 | Medio | PIN in chiaro, `session_secret` inutilizzato, sessioni in memoria di processo, `restricted_topics` mai applicato, `debug: true`, nessun header di sicurezza. | Aperto |

### Fino alla v0.1.0

Se stai usando Shinra oggi:

1. **`/api/alexa` ora si difende da solo**, ma richiede `SHINRA_ALEXA_SKILL_ID`
   in `.env`: senza, rifiuta ogni richiesta invece di accettarle tutte.
2. Tieni il servizio su una rete di cui ti fidi, o dietro un reverse proxy che
   richieda autenticazione a monte.
3. Usa un token Home Assistant dedicato, cosi' da poterlo revocare da solo.
4. Prima di ogni `git commit -a`, verifica che `config/config.yaml` non sia nel diff.

---

## Principi permanenti

1. **Nessun segreto nel repository.** I segreti stanno in `.env` o nell'ambiente.
2. **Protetto per difetto.** Un endpoint e' pubblico solo se dichiarato tale.
3. **Il modello non e' fidato.** Un `entity_id` prodotto dall'LLM viene validato
   contro le entita' reali prima di raggiungere Home Assistant.
4. **Ogni azione lascia traccia.** Dalla `0.2.0` esiste un registro di chi ha
   comandato cosa, da quale canale e quando.
5. **L'audio resta in casa.** Dalla `0.4.0` nessun flusso vocale lascia la rete
   locale: e' la promessa che il progetto fa fin dal README.
