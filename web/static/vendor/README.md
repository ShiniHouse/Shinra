# Librerie di terze parti

File copiati qui **senza modifiche**, serviti dal nostro server: la dashboard non carica
niente da CDN esterni (non funzionerebbe senza internet, e chi controlla il CDN potrebbe
cambiarne il comportamento). La versione sta nel nome del file, cosi' un aggiornamento e'
un file nuovo e nessuna cache serve quello vecchio.

| File | Origine | Versione | Licenza | SHA-256 |
| :--- | :--- | :--- | :--- | :--- |
| `lucide-0.344.0.min.js` | pacchetto npm `lucide`, `dist/umd/lucide.min.js` | 0.344.0 | ISC (nota di copyright nell'intestazione del file) | `7c973be50ea92f69da298e017e01e8e6a068f8b599ee087041181f151c8ef092` |

**Come e' stato verificato:** scaricato da jsDelivr e, separatamente, estratto dal tarball
`lucide-0.344.0.tgz` del registro npm: i due file sono identici byte per byte.

**Aggiornare lucide:** scarica la versione nuova con lo stesso procedimento, aggiungi il file
qui, cambia il nome in `web/templates/index.html` e in `sw.js`, e rigenera l'elenco delle icone
valide con `python scripts/aggiorna_icone.py` (una guardia fallisce se non coincidono).
