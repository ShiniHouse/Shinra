# Registro delle decisioni architetturali

Un ADR (*Architecture Decision Record*) fissa una scelta strutturale, il suo
contesto e le sue conseguenze. Serve a rispondere fra sei mesi alla domanda
«perche' e' fatto cosi'?» senza ricostruirlo dal codice.

Si scrive un ADR quando una scelta e' **difficile da invertire** o quando sono
state scartate alternative ragionevoli. Non serve per le decisioni ovvie.

- Numerazione progressiva a quattro cifre, mai riutilizzata.
- Uno stato: `Proposto`, `Accettato`, `Sostituito da NNNN`.
- Un ADR accettato non si modifica: se la decisione cambia, se ne scrive uno
  nuovo che sostituisce il precedente.

| N. | Titolo | Stato |
| :--- | :--- | :--- |
| [0001](0001-versionamento-e-flusso-di-lavoro.md) | Versionamento semantico e GitHub Flow | Accettato |
| [0002](0002-sqlite-al-posto-dei-file-json.md) | SQLite al posto della persistenza su file JSON | Accettato |
| [0003](0003-scheduler-persistente.md) | Scheduler persistente in processo | Accettato |
| [0004](0004-identita-ruoli-e-permessi.md) | Identita' per persona, ruoli personalizzati e dispositivi fidati | Accettato |
