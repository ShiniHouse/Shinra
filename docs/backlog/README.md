# Backlog

Ogni file di questa cartella e' una issue pronta da aprire su GitHub: titolo,
etichette, milestone, contesto, lavoro da fare e criteri di accettazione.

Il backlog e' versionato nel repository per due ragioni: resta leggibile senza
accedere a GitHub, e le modifiche al piano di lavoro passano da una PR come
tutto il resto.

## Struttura di un file

L'intestazione YAML contiene i metadati usati dallo script di importazione.
Il corpo e' il testo della issue.

Il campo `issue` e' il numero che GitHub ha assegnato: lo scrive
`import_backlog.py` subito dopo aver creato la issue, e **non si modifica a
mano**. Il numero nel nome del file deve coincidere con quello, e c'e' un test
che lo verifica (`tests/unit/test_backlog.py`).

Non e' pignoleria. Il numero lo decide GitHub, non l'ordine in cui abbiamo
scritto i file: tre schede aggiunte dopo la prima importazione hanno ricevuto
i numeri 46, 47 e 48 pur chiamandosi `19-`, `20-` e `34-`. I numeri 19 e 20
erano gia' altre due issue della v0.3.0, e due commit che scrivevano
`Closes #19` e `Closes #20` intendendo le schede hanno chiuso come completate
due lavori che nessuno aveva iniziato.

Quando si aggiunge una scheda nuova, la si chiama con un numero qualunque
(l'ultimo piu' uno va bene), si esegue l'importazione, e **poi** si rinomina
il file con il numero che GitHub ha dato.

## Importazione su GitHub

Serve [GitHub CLI](https://cli.github.com/) autenticato:

```bash
gh auth status                       # verifica l'accesso
python scripts/import_backlog.py     # crea milestone, etichette e issue
```

Lo script e' idempotente: rieseguirlo non duplica le issue gia' create,
riconosciute dal titolo.

## Etichette

| Etichetta | Significato |
| :--- | :--- |
| `tipo: difetto` | Qualcosa non funziona |
| `tipo: attivita'` | Lavoro pianificato in roadmap |
| `tipo: funzione` | Capacita' nuova |
| `area: sicurezza` | Autenticazione, segreti, superficie di attacco |
| `area: core` | Agente, tool, motori |
| `area: infra` | Database, scheduler, packaging, CI |
| `area: frontend` | Interfaccia web e PWA |
| `area: integrazioni` | Alexa, Home Assistant, canali |
| `area: documentazione` | Documenti e guide |
| `gravita': critica` | Blocca l'uso o espone la casa |
| `gravita': alta` | Compromette una funzione principale |
| `gravita': media` | Degrado o rischio contenuto |
| `stato: da valutare` | Non ancora accettata in roadmap |
| `buona prima issue` | Adatta a chi si avvicina al progetto |
