# Backlog

Ogni file di questa cartella e' una issue pronta da aprire su GitHub: titolo,
etichette, milestone, contesto, lavoro da fare e criteri di accettazione.

Il backlog e' versionato nel repository per due ragioni: resta leggibile senza
accedere a GitHub, e le modifiche al piano di lavoro passano da una PR come
tutto il resto.

## Struttura di un file

L'intestazione YAML contiene i metadati usati dallo script di importazione.
Il corpo e' il testo della issue.

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
