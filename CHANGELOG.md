# Changelog

Tutte le modifiche rilevanti a questo progetto sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e il progetto adotta il [Versionamento Semantico](https://semver.org/lang/it/).

Fino alla `1.0.0` il progetto e' in **beta**: le versioni `0.x` possono
introdurre modifiche incompatibili fra una minor e l'altra. Ogni minor
corrisponde a una fase della [roadmap](docs/ROADMAP.md) ed e' comunque
installabile e utilizzabile.

---

## [Non rilasciato]

### Sicurezza
- **I segreti non stanno piu' nel repository** (issue #07, SEC-05).
  `config/config.yaml`, `data/users.json`, `data/knowledge.json` e gli altri
  file di stato non sono piu' tracciati da git. Token di Home Assistant, PIN
  amministratore e segreto di sessione si leggono dall'ambiente o da `.env`,
  con precedenza `ambiente > .env > config.yaml`.
- `save_config()` non puo' piu' scrivere un segreto nel file di
  configurazione: e' l'invariante che impediva a un `git commit -a` di
  pubblicare le credenziali di casa.
- Rimosso il segreto di sessione predefinito `shinra-secret-key-salt`, uguale
  per ogni installazione. Ne viene generato uno per installazione al primo
  avvio e scritto in `.env` con permessi `600`.
- I segreti rimasti in `config.yaml` da versioni precedenti vengono spostati
  in `.env` al primo avvio e cancellati da li'. La migrazione e' idempotente.
- Controlli d'avvio: token mancante con Home Assistant attivo, PIN mancante con
  autenticazione attiva, `debug` esposto in rete, skill Alexa senza `skill_id`.
  Vengono segnalati nel log e non impediscono l'avvio — un hub domotico che si
  rifiuta di partire lascia una casa senza controllo.
- Il controllo dei segreti in CI accetta una dichiarazione esplicita per i
  valori deliberatamente finti: `# pragma: allowlist secret` sulla stessa riga.
  Serviva perche' il token di prova nei test — che ha la forma di un JWT
  proprio per somigliare al caso reale — faceva scattare il controllo. La
  dichiarazione e' visibile in revisione; escludere intere cartelle no, e un
  segreto vero puo' finire in un test tanto quanto altrove.
- La configurazione illeggibile non viene piu' ignorata in silenzio: prima un
  file corrotto faceva ripartire dai valori predefiniti senza alcun segnale.

### Aggiunto
- `data/examples/` con i valori iniziali versionati. Al primo avvio ogni file
  mancante in `data/` viene creato copiando il proprio esempio, cosi'
  un'installazione nuova parte pronta e una esistente non viene toccata.
- Impianto di progetto: `pyproject.toml` con dipendenze, dipendenze di
  sviluppo e configurazione di ruff, black, pytest, coverage e mypy.
- Documenti di governance: `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`,
  `CONTRIBUTING.md`, `SECURITY.md`, questo changelog.
- Registro delle decisioni architetturali in `docs/adr/`.
- Backlog completo delle cinque milestone in `docs/backlog/`.
- Integrazione continua GitHub Actions: lint, formattazione, type check e test.
- Template per issue e pull request.
- Suite di test iniziale, con i test di regressione dei difetti bloccanti
  marcati `xfail(strict=True)` finche' non vengono corretti.
- `.env.example` per la migrazione dei segreti fuori dal file di configurazione.
- `scripts/deploy.sh`: aggiornamento del server Debian con backup, distribuzione
  per tag di release, verifica di salute e ritorno automatico alla versione
  precedente se il servizio non risponde.
- `deploy/shinra.service`: unita' systemd irrobustita, con utente dedicato al
  posto di root, segreti da `.env` e filesystem in sola lettura.
- `docs/DEPLOY.md`, che include la messa in sicurezza da eseguire sul server
  **prima** di unire la issue #07: quel commit rimuove `config/config.yaml`
  dall'indice, e il primo `git pull` successivo lo cancellerebbe dal server
  insieme al token di Home Assistant.

### Modificato
- Formattato l'intero codice Python con black (26 file). Il commit e' puramente
  meccanico: nessun cambiamento di comportamento. Elencato in
  `.git-blame-ignore-revs` perche' non sporchi `git blame`.
- Ridotto l'insieme di regole ruff a quello che il codice esistente puo'
  sostenere. Le regole di modernizzazione (`UP`, 186 rilievi) vengono attivate
  durante il riordino della v0.2.0: una regola che nessuno riesce a soddisfare
  viene solo disattivata.
- `.gitignore` ora esclude `config/config.yaml` e i file di stato con dati
  personali. **Attenzione**: `config/config.yaml` risulta ancora tracciato da
  git; la rimozione dall'indice fa parte della v0.1.0.

---

## Versioni pianificate

| Versione | Nome | Obiettivo |
| :--- | :--- | :--- |
| `0.1.0` | Impianto chiuso | Difetti bloccanti risolti, superficie di attacco chiusa, segreti fuori da git |
| `0.2.0` | Fondamenta | Scheduler persistente, database, memoria per sessione, layout a pacchetto, test |
| `0.3.0` | Copertura | Eventi Home Assistant in tempo reale e i domini oggi scoperti |
| `0.4.0` | Proattivita' | Motore di regole, notifiche push, voce interamente locale |
| `0.5.0` | Prodotto | Frontend modulare, backup, internazionalizzazione, distribuzione |
| `1.0.0` | Stabile | Criteri di uscita in `docs/ROADMAP.md` soddisfatti |

Le sette funzioni complementari (consulente energetico, check-in presenza,
registro di casa, briefing per profilo, spiegabilita', contesto cucina, diario
della casa) sono programmate **dopo** la `1.0.0`.
