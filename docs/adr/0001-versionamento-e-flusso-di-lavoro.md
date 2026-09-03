# 0001 — Versionamento semantico e GitHub Flow

- **Stato:** Accettato
- **Data:** 2026-09-03

## Contesto

Il repository ha ventinove commit, nessun tag, un solo branch e nessuna
integrazione continua. Il lavoro procede a commit diretti su `main`. Due difetti
bloccanti — chiamate a metodi inesistenti — sono arrivati fino allo stato
corrente senza che nulla li intercettasse.

Il progetto entra ora in una fase di risanamento e ampliamento che durera'
diverse settimane e passera' per cambiamenti strutturali profondi (database,
scheduler, riorganizzazione a pacchetto). Serve un modo per sapere in che stato
si trova il sistema in un dato momento e per impedire che un difetto certo
raggiunga di nuovo `main`.

## Decisione

**Versionamento semantico**, con una minor per ogni fase della roadmap:
`0.1.0` → `0.2.0` → `0.3.0` → `0.4.0` → `0.5.0` → `1.0.0`. Fino alla `1.0.0` il
progetto e' in beta e una minor puo' introdurre modifiche incompatibili. Ogni
minor e' comunque installabile e utilizzabile: non esistono tag intermedi rotti.

**GitHub Flow**: `main` protetto e sempre rilasciabile, ogni lavoro su un branch
tematico, integrazione tramite Pull Request con CI verde obbligatoria.

**Conventional Commits**, perche' il changelog derivi dai messaggi invece di
essere ricostruito a mano.

## Alternative considerate

**Git Flow completo** (`main` + `develop` + `release/` + `hotfix/`). Scartato:
con uno sviluppatore aggiunge quattro passaggi per ogni modifica senza risolvere
nessun problema reale. Il branch `develop` ha senso quando esistono rilasci
paralleli da mantenere, che qui non ci sono.

**Continuare a committare su `main`.** Scartato: e' esattamente il processo che
ha lasciato passare BLK-01 e BLK-02.

**Granularita' fine dei tag** (una minor per gruppo di lavoro, fino a `0.9`).
Scartato: moltiplica la cerimonia di rilascio senza aumentare l'informazione,
perche' le fasi sono gia' l'unita' naturale di completamento.

## Conseguenze

**Positive.** Lo stato del sistema e' leggibile dal tag. La CI diventa il punto
in cui un difetto certo viene fermato. Il changelog e' un sottoprodotto del
lavoro, non un compito separato.

**Negative.** Ogni modifica costa una PR, anche la correzione di un refuso. E'
il prezzo accettato per avere un cancello unico verso `main`.

**Da fare.** Attivare la protezione del branch `main` su GitHub con CI
obbligatoria — non e' automatica e va configurata nelle impostazioni del
repository.
