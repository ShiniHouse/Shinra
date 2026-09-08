# Come si lavora su Shinra

Il progetto e' in beta e procede per fasi verso la `1.0.0`. Questo documento e'
il contratto di lavoro: rispettarlo e' cio' che impedisce che tornino i difetti
gia' corretti.

---

## 1. Ambiente

```bash
git clone https://github.com/ShiniHouse/Shinra.git
cd Shinra

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
pre-commit install

cp config/config.example.yaml config/config.yaml
cp .env.example .env               # e compilare i segreti
```

`config/config.yaml` e `.env` non sono versionati e non devono mai esserlo.

---

## 2. Flusso di lavoro: GitHub Flow

`main` e' sempre rilasciabile ed e' protetto. Non si committa mai direttamente.

```bash
git switch main && git pull
git switch -c fix/blk-01-add-knowledge-item
# ... lavoro, con commit piccoli ...
git push -u origin fix/blk-01-add-knowledge-item
# apertura della Pull Request, CI verde, merge
```

### Nome del branch

`<tipo>/<slug-breve>` — dove il tipo e' uno di:

| Tipo | Uso |
| :--- | :--- |
| `feat/` | Funzionalita' nuova |
| `fix/` | Correzione di un difetto |
| `refactor/` | Riorganizzazione senza cambiamento di comportamento |
| `perf/` | Prestazioni |
| `test/` | Solo test |
| `docs/` | Solo documentazione |
| `chore/` | Impianto, dipendenze, CI |
| `security/` | Correzione di sicurezza |

Quando il branch chiude una issue, includerne il numero: `fix/12-scheduler-persistente`.

---

## 3. Messaggi di commit

[Conventional Commits](https://www.conventionalcommits.org/it/v1.0.0/). Il tipo
determina il posto della voce nel changelog.

```text
<tipo>(<ambito>): <cosa cambia, imperativo, minuscolo>

<corpo facoltativo: perche', non come>

Closes #12
```

Esempi presi dal backlog reale:

```text
fix(data-store): aggiunge add_knowledge_item mancante

Il motore dell'intervista chiamava un metodo inesistente, causando un 500
a ogni risposta dell'utente. Vedi BLK-01.

Closes #1
```

```text
security(api): richiede autenticazione su tutti gli endpoint di gestione

Sostituisce il controllo manuale presente sul solo POST /api/settings con
una dipendenza FastAPI applicata all'intero router.

Closes #3
```

Una modifica incompatibile si segnala con `!` dopo l'ambito e una nota
`BREAKING CHANGE:` nel corpo.

---

## 4. Cosa deve essere vero prima di aprire una Pull Request

- [ ] `ruff check .` senza errori
- [ ] `black --check .` senza differenze
- [ ] `pytest` verde
- [ ] `mypy src/shinra/config src/shinra/domain src/shinra/infra src/shinra/services src/shinra/skills`
      senza errori — e' un passo **bloccante** della CI, e mancava da questo
      elenco: una PR e' arrivata rossa proprio perche' chi la scriveva aveva
      eseguito gli altri tre e non questo. Non sta fra i ganci pre-commit
      perche' mypy ha bisogno delle dipendenze installate per vedere i tipi:
      dentro un gancio darebbe risposte diverse da quelle della CI, ed e'
      esattamente il difetto che `tests/unit/test_stile.py` presidia per
      ruff e black
- [ ] I nuovi comportamenti hanno almeno un test; le correzioni hanno un test
      che **fallisce senza la correzione**
- [ ] Nessun segreto nel diff (token, PIN, indirizzi IP privati, nomi di persone reali)
- [ ] `CHANGELOG.md` aggiornato sotto `[Non rilasciato]`
- [ ] Se la struttura cambia, `docs/ARCHITECTURE.md` e' aggiornato
- [ ] Se una scelta non e' ovvia, esiste un ADR in `docs/adr/`
- [ ] La descrizione della PR chiude la issue con `Closes #NN`, dove `NN` e'
      il numero scritto nell'intestazione della scheda di backlog (vedi sotto)

Una PR fa **una cosa sola**. Una PR che corregge un difetto e riorganizza tre
moduli va divisa in due.

### Chiudere la issue

La chiusura va nella **descrizione della PR**, non nel messaggio di commit:

```
Closes #46
```

Due errori gia' commessi, entrambi con lo stesso rimedio.

Scrivere `Chiude #46` in italiano non chiude niente: GitHub riconosce solo le
sue parole (`Closes`, `Fixes`, `Resolves`). Le issue restano aperte, la
milestone resta indietro, e si scopre settimane dopo guardando una
percentuale.

Il numero va preso dall'**intestazione della scheda** (`issue: 46`), mai dal
nome del file. I due hanno smesso di coincidere quando sono state aggiunte
schede dopo la prima importazione, e due commit che dicevano `Closes #19` e
`Closes #20` intendendo i file hanno chiuso come completate due issue della
`v0.3.0` che nessuno aveva iniziato. Adesso il numero e' nell'intestazione,
`import_backlog.py` ce lo scrive da solo e `tests/unit/test_backlog.py`
fallisce se torna a divergere — ma il numero si legge da li'.

Per la reazione opposta: scrivere `Riferimento: issue #46` non chiude niente
neanche lui. E' utile in un commit, che non deve chiudere; nella descrizione
della PR serve la parola vera.

---

## 5. Test

```bash
pytest                      # tutto tranne quelli marcati network/integration
pytest -m "not network"     # esplicito, come in CI
pytest --cov                # con copertura
```

Regole:

- I test unitari **non toccano la rete**. Le chiamate HTTP si simulano con `respx`.
- I test che richiedono Internet portano il marcatore `@pytest.mark.network`;
  quelli che richiedono Ollama o Home Assistant attivi `@pytest.mark.integration`.
  Entrambi sono esclusi in CI.
- Un difetto noto ancora da correggere si documenta con un test
  `@pytest.mark.xfail(strict=True)`: quando la correzione arriva, il test
  diventa rosso finche' non si rimuove il marcatore. E' il modo in cui il
  progetto garantisce che nessun difetto venga dichiarato risolto senza prova.

---

## 6. Rilascio di una versione

Le versioni escono a fine fase, secondo `docs/ROADMAP.md`.

1. Verificare che tutti i criteri di uscita della fase siano soddisfatti.
2. Spostare le voci da `[Non rilasciato]` a `[X.Y.Z] - AAAA-MM-GG` nel changelog.
3. Aggiornare `version` in `pyproject.toml` (da `X.Y.Z.dev0` a `X.Y.Z`).
4. PR di rilascio, CI verde, merge.
5. Tag e pubblicazione:

```bash
git switch main && git pull
git tag -a v0.1.0 -m "v0.1.0 — Impianto chiuso"
git push origin v0.1.0
gh release create v0.1.0 --title "v0.1.0 — Impianto chiuso" --notes-file docs/release/v0.1.0.md
```

6. Riportare `pyproject.toml` alla `dev0` della minor successiva.

---

## 7. Sicurezza

Una vulnerabilita' non si segnala mai in una issue pubblica: vedi `SECURITY.md`.

Tre regole non negoziabili in ogni PR:

1. Nessun segreto nel repository. I segreti stanno in `.env` o nell'ambiente.
2. Ogni endpoint nuovo dichiara esplicitamente se e' pubblico. In assenza di
   dichiarazione, e' protetto.
3. Ogni input che raggiunge Home Assistant e' validato. Un `entity_id` che
   arriva dal modello non e' un dato fidato.

---

## Protezione del ramo `main`

La CI verde non basta se si puo' unire lo stesso. La protezione si attiva
una volta sola, dal proprietario del repository:

```bash
gh api -X PUT repos/ShiniHouse/Shinra/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=Lint e formattazione" \
  -f "required_status_checks[contexts][]=Ganci pre-commit" \
  -f "required_status_checks[contexts][]=Test — Python 3.10" \
  -f "required_status_checks[contexts][]=Test — Python 3.11" \
  -f "required_status_checks[contexts][]=Test — Python 3.12" \
  -f "required_status_checks[contexts][]=Controllo segreti" \
  -F "enforce_admins=false" \
  -F "required_pull_request_reviews=null" \
  -F "restrictions=null"
```

`enforce_admins=false` e' voluto: in un progetto con un solo manutentore,
bloccare anche l'amministratore significa non poter piu' rimediare a una CI
rotta se non disattivando la protezione. Il resto vale comunque, perche' il
lavoro passa dalle pull request.
