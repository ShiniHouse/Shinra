# Guida allo sviluppo

Come si aggiunge una cosa a Shinra **senza leggere il codice dell'agente**. Ogni
sezione e' una ricetta: cosa toccare, in che ordine, e quale test ti dice che
hai dimenticato un pezzo.

Prima di cominciare: [`CONTRIBUTING.md`](../CONTRIBUTING.md) dice come si
lavora (branch, commit, Pull Request) e [`ARCHITECTURE.md`](ARCHITECTURE.md)
perche' il codice e' diviso cosi'. Qui c'e' il *come*.

---

## 0. Prima di toccare qualcosa

```bash
pip install -e ".[dev]"    # Python: dipendenze e attrezzi
npm ci                     # solo se tocchi il frontend
```

Le stesse verifiche che fa la CI, in locale:

```bash
ruff check . && black --check .                 # stile
mypy src/shinra
python -m pytest tests/unit -q                  # i test
npm run lint && npm run formato && npm run gesti   # frontend (gesti: serve un browser)
```

`pytest` impiega un paio di minuti. Se ne tocchi un pezzo solo, `-k` e il nome
del file bastano per iterare; prima della Pull Request gira tutto.

### Dove sta cosa

La regola e' una sola: **le frecce vanno in una direzione** e
`tests/unit/test_architettura.py` la verifica a ogni esecuzione.

| Cartella | Cosa ci va | Non deve conoscere |
| :--- | :--- | :--- |
| `src/shinra/domain/` | Regole pure: calcoli, validazioni, il grafo delle routine | Niente IO: ne' rete, ne' database, ne' FastAPI |
| `src/shinra/infra/` | Il mondo esterno: database, Home Assistant, Ollama, scheduler, Whisper | `services/` |
| `src/shinra/skills/` | Gli strumenti che il modello puo' chiamare | Rotte e canali |
| `src/shinra/services/` | L'agente, gli intenti, i permessi, il registro, i motori | — |
| `src/shinra/api/` e `channels/` | FastAPI, Alexa | `infra/` direttamente |
| `web/static/js/` | La dashboard: un modulo ES per area | — |
| `migrazioni/` | Alembic | — |

---

## 1. Aggiungere uno strumento (tool) che il modello puo' chiamare

E' la cosa che si fa piu' spesso: «controlla il robot aspirapolvere»,
«leggi le scadenze». Un tool e' una funzione che il modello sceglie per nome.

**1. Il modulo.** Un file in `src/shinra/skills/`, con una funzione che
restituisce un dizionario. Per convenzione, `{"success": True, ...}` se e'
andata bene e `{"success": False, "error": "..."}` se no: e' come
`execute_tool` capisce se scrivere nel registro «riuscito» o «errore».
Non sollevare per un guasto previsto: restituiscilo.

```python
# src/shinra/skills/esempio.py
from typing import Any, Dict


async def saluta(nome: str) -> Dict[str, Any]:
    if not nome.strip():
        return {"success": False, "error": "Dimmi chi devo salutare."}
    return {"success": True, "message": f"Ciao {nome}!"}
```

**2. La registrazione — nel modulo del tuo dominio in
`src/shinra/skills/catalogo/`, tre punti.** Gli strumenti sono divisi per
dominio (`casa`, `clima_e_tapparelle`, `energia`, `agenda`, `informazioni`…):
scegli quello giusto, o creane uno nuovo e aggiungilo a `skills/registry.py`,
che li mette insieme. In quel file:

- l'`import` della funzione in cima;
- una voce in `GESTORI` (nome che il modello usa → funzione);
- uno schema in `SCHEMI` (il formato delle funzioni di Ollama/OpenAI):
  nome, descrizione, parametri, e quali sono obbligatori.

`TOOL_HANDLERS` e `TOOLS_SCHEMA` in `registry.py` sono la somma di tutti i
domini: sono quelli che l'agente e i test leggono.

La **descrizione** dello schema e' la cosa piu' importante: e' l'unica che il
modello legge per decidere *quando* chiamarti. Scrivila come a una persona
che non sa niente della casa.

**3. Il prompt.** Se il tool e' di un dominio che il modello deve sapere
scegliere, aggiungi una riga a `prompt.regole` in **tutti** i file di
`src/shinra/infra/lingue/` (`it.yaml`, `en.yaml`). Il nome del tool
resta identico in ogni lingua: e' codice.

**4. I permessi.** Se il tool comanda un dispositivo di Home Assistant, il
controllo e' gia' fatto: passa da `client_home_assistant().call_service`, che
esige il permesso del dominio (`dispositivi.comanda`, `sicurezza.comanda`…) **con
l'identita' di chi ha chiesto**. Non riscriverlo. Se invece il tool fa
qualcos'altro di sensibile, chiama `esigi(profilo_corrente(), permesso)` da
`shinra.services.permessi`: solleva `PermessoNegato` e scrive il rifiuto nel
registro; `execute_tool` lo traduce in una risposta leggibile.

**5. Di' se puo' scegliere da solo.** Aggiungi il nome del tool a `TOOL_SICURI`
in `src/shinra/domain/sensibilita.py` se non apre e non disarma niente, qualunque
argomento riceva; a `TOOL_CONDIZIONATI` (e a `classifica`) se dipende dagli
argomenti, come una tapparella che puo' essere un garage. **Uno strumento che
non e' in nessuno dei due elenchi e' sensibile**: non parte finche' una persona
non risponde «si'» (issue #192), e `test_ogni_strumento_del_registro_e_classificato`
fallisce finche' non decidi. Il modello non e' fidato: su serrature, allarme e
garage quello che ha scelto non basta.

**6. Gratis.** Ogni chiamata passa da `execute_tool`, che la scrive nel
registro delle azioni (chi, cosa, quando, da quale canale, con che esito). Non
devi farlo tu, ed e' per questo che non va aggirata.

**7. I test.** Un caso riuscito e uno d'errore, con le chiamate di rete
simulate: nessuna rete nei test unitari. Esempio da copiare:
`tests/unit/test_domini_casa.py`. Due guardie ti dicono se hai dimenticato
qualcosa: `test_ogni_schema_ha_il_suo_gestore` (uno schema senza funzione) e
`tests/unit/test_guida_sviluppo.py`, che esegue questa stessa ricetta.

---

## 2. Aggiungere un intento (un percorso rapido che salta il modello)

Un intento riconosce una frase e risponde da solo: «accendi la luce», «che
tempo fa». Serve quando la frase e' frequente e il modello e' lento.

**1.** Una classe in `src/shinra/services/intenti/` che estende `Intento` e
implementa `applicabile(richiesta)` (veloce, niente rete) ed `esegui(richiesta)`
(restituisce una `Risposta`, oppure `None` per «non era per me»).
`priorita` piu' bassa vuol dire «guarda prima me».

**2.** `registra(MioIntento())` in fondo al file.

**3. Non scrivere parole nel codice.** Le parole che riconoscono la frase e le
frasi che l'intento dice vanno in `lingue/it.yaml` e `lingue/en.yaml`, e si
leggono da `richiesta.schemi`. Una chiave nuova si dichiara nel caricatore
(`RICHIESTE` per gli schemi, `CHIAVI_MESSAGGI` per le frasi): cosi' una lingua
che non ce l'ha non si carica, invece di scoppiare in mezzo a una risposta.

**4. Test.** Guarda `tests/unit/test_intenti.py` e
`tests/unit/test_lingua_per_utente.py`: il secondo mostra come provare lo
stesso intento con due persone di lingue diverse.

---

## 3. Aggiungere una lingua

Un file `src/shinra/infra/lingue/<codice>.yaml` con **le stesse
chiavi** di `it.yaml`. Non si tocca il codice: lo prova un test che ne inventa
una. Il caricatore dice per nome quale chiave manca.

Le sezioni `tempo` e `timer` sono le parole del tempo: i numeri in lettere, le unita', i nomi dei giorni e dei mesi, «domani»,
«stasera», e le frasi che chiedono un timer o un promemoria. Il parser (`domain/quando.py`) non conosce nessuna parola:
legge il `Lessico` della lingua, e un test controlla che nessuna parola italiana resti nel dominio (#205).

La lingua si sceglie per persona nella scheda del profilo, o per tutta la casa
con `assistant.language`. Restano italiani, per ora: le etichette della dashboard e i messaggi degli strumenti (l'intervista no, #207).
Gli strumenti che leggono il tempo (promemoria, calendario, scadenze) usano la lingua dell'installazione.

La sezione `intervista` e' l'intervista di apprendimento: ogni passo (titolo, domanda, suggerimento, parole di «la casa
lo sa gia'»), ogni frase (`testi`), le parole di sì/no/salta, i nomi dei comandi di una routine e il prompt di estrazione
per il modello. Una lingua nuova la traduce per intero, e il caricatore dice per nome cosa manca. In YAML `no` senza
apici e' «falso»: la chiave delle negazioni si chiama `nega`.

---

## 4. Aggiungere una rotta HTTP

**1.** In uno dei file `src/shinra/api/routes_*.py` — per area: `routes_utenti`,
`routes_casa`, `routes_impostazioni`, `routes_attivita`… — o in uno nuovo, incluso
con `app.include_router(...)` in `app.py`.

**2. Protetta per difetto.** I router si dichiarano con la dipendenza di
autenticazione; una rotta e' pubblica solo se lo dici. Per limitarla a chi ha
un permesso:

```python
@router.post("/cosa", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_UTENTI))])
async def fai_cosa(dati: MioModello):
    """Una frase che dice cosa fa: finisce nel riferimento delle API."""
```

**3. Una riga di documentazione.** La prima frase della docstring e' il testo
della tabella in [`API.md`](API.md). Senza, un test fallisce.

**4. Rigenera il riferimento:** `python scripts/genera_api.py`. Un test
(`test_documentazione_api`) confronta il file con le rotte vere.

**5. Test con un client vero.** La fixture `cliente_autenticato`
(`tests/conftest.py`) entra in casa come la dashboard. Vedi
`tests/unit/test_api_regole.py`.

---

## 5. Toccare il database

Il database e' SQLite con SQLAlchemy sincrono ([ADR 0005](adr/0005-sqlalchemy-sincrono.md)).

**1.** Il modello in `src/shinra/infra/db/modelli.py`. Una colonna nuova ha
sempre `server_default`, altrimenti la migrazione non puo' riempire le righe
che esistono.

**2.** Se e' una colonna di un'anagrafica, il nome va anche nell'elenco
`campi` del deposito in `infra/db/depositi.py`, o si scrive e non si rilegge.

**3.** Una migrazione in `migrazioni/versions/`, numerata, che punta alla
precedente (`down_revision`). Guarda l'ultima per la forma: usa
`batch_alter_table`, perche' SQLite non sa modificare una tabella in altro
modo. Scrivi anche `downgrade()`, e dì cosa si perde.

**4.** `test_archivio.py` confronta i modelli con cio' che le migrazioni
producono: se hai cambiato il modello e dimenticato la migrazione, fallisce e
dice `alembic revision --autogenerate`.

Al primo avvio l'applicazione migra il database da sola.

---

## 6. Aggiungere un'area alla dashboard

La dashboard non ha bundler ([ADR 0006](adr/0006-niente-bundler.md)): moduli ES
serviti cosi' come stanno.

**1.** Un file `web/static/js/<area>.js`. Importa da altri moduli quello che
ti serve (`import { Stato } from './stato.js';`) ed esporta con `export` solo
cio' che un altro modulo importa. Niente variabili globali: lo stato che
attraversa le aree sta in `Stato` (`stato.js`).

**2.** Aggiungi `import './<area>.js';` in `principale.js`. Un modulo non
importato da nessuno non gira, e non da' nessun errore.

**3. Il markup non esegue codice.** Mai `onclick="..."`. Si nomina un gesto:

```html
<button data-gesto="salvaCosa" data-args="${_args(id)}">Salva</button>
```

e in fondo al modulo lo si registra: `Gesti.registra({ salvaCosa });`. Gli
argomenti viaggiano come JSON in `data-args` (`_args(...)` dentro un template
`_html`). Eventi: `data-gesto` (clic), `data-al-cambio`, `data-mentre-scrivi`,
`data-all-invio`, e per l'editor a nodi `data-al-premere` e `data-al-rilascio`.

**4. Ogni valore che arriva da fuori passa da `_html`.** Il tag `_html`
ripulisce tutto cio' che interpoli; un pezzo di markup scritto da te si marca
con `_grezzo(...)`. Mai `innerHTML = \`...${valore}...\``.

**5. Un file non supera le cinquecento righe.** Lo dice un test.

**6. Verifica:** `npm run lint`, `npm run formato`, i test Python del frontend
(`tests/unit/test_frontend_*.py`, uno per area) e, se tocchi un gesto, un test in
`tests/gesti/` (un browser vero: un clic che un antenato si mangia non si vede
nel sorgente).

---

## 6 bis. Cambiare lo stile (le classi Tailwind)

Le classi Tailwind dei template e dei copioni non vengono costruite nel browser: il foglio
`web/static/css/tailwind.css` e' **generato e committato**. Se aggiungi o cambi una classe
(`bg-indigo-600`, `w-[137px]`, `md:grid-cols-3`...) devi rigenerarlo:

```bash
npm ci          # una volta
npm run css     # riscrive web/static/css/tailwind.css
```

Se te ne dimentichi la pagina perde quello stile **senza nessun errore** — la classe c'e' nel
sorgente e non nel CSS — e per questo la CI esegue `npm run css:verifica`, che rigenera il file e
lo confronta: fallisce dicendo di eseguire `npm run css`. La configurazione (colori `brand` e
`amber`, i caratteri, `darkMode: 'class'`) sta in `tailwind.config.js`. Una classe costruita a
pezzi (`'bg-' + colore + '-500'`) non si vede: scrivila intera.

---

## 7. Decisioni e documenti

- **Una scelta difficile da invertire**, o con alternative scartate: un ADR in
  `docs/adr/` (numerato, mai riutilizzato) e una riga nel suo indice.
- **Una modifica visibile a chi usa Shinra:** una voce nel `CHANGELOG.md`.
- **Lavoro pianificato:** una scheda in `docs/backlog/<versione>/`, poi
  `python scripts/import_backlog.py` la trasforma in issue e scrive il numero
  nella scheda. Non si modifica a mano.
- **Una guida nuova** va elencata nel README, o un test fallisce.

---

## 8. Cosa ti dicono i test quando dimentichi qualcosa

| Hai dimenticato… | Fallisce |
| :--- | :--- |
| Il gestore di un tool (o lo schema) | `test_ogni_schema_ha_il_suo_gestore` |
| Di rigenerare `API.md` | `test_il_riferimento_nel_repository_e_aggiornato` |
| Una riga di spiegazione su una rotta | `test_ogni_rotta_dice_cosa_fa` |
| Una chiave in una lingua | il caricatore, per nome; `test_ogni_lingua_ha_le_stesse_frasi_e_gli_stessi_pezzi_di_prompt` |
| La migrazione di un modello | `test_archivio.py` |
| Di registrare un gesto | `test_ogni_gesto_chiesto_dal_markup_e_registrato` |
| Di importare un modulo in `principale.js` | `test_il_punto_d_ingresso_importa_ogni_area_una_volta_sola` |
| Di esportare un nome importato | `test_ogni_modulo_e_raggiungibile_e_ogni_nome_importato_esiste` |
| Una dipendenza che viola i livelli | `test_nessuna_dipendenza_nuova_fra_livelli` |
| Un a capo finale in fondo a un file | `test_stile.py` |
| Un file del frontend sopra le cinquecento righe | `test_nessun_pezzo_del_frontend_supera_le_cinquecento_righe` |
| Di rigenerare il CSS dopo aver cambiato delle classi | `npm run css:verifica` (in CI, nel job ESLint) |
