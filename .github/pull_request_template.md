## Cosa cambia

<!-- Una frase. Se ne servono tre, probabilmente questa PR fa piu' di una cosa. -->

Closes #

## Perche'

<!-- Il problema che risolve, non l'elenco dei file toccati. -->

## Come verificarlo

<!-- I passi esatti per riprodurre il comportamento nuovo o corretto. -->

1.
2.

## Lista di controllo

- [ ] `ruff check .` e `black --check .` non segnalano nulla
- [ ] `pytest` e' verde
- [ ] Se e' una correzione: esiste un test che **fallisce senza questa PR**
- [ ] Se e' una funzione nuova: e' coperta da test
- [ ] Nessun segreto nel diff (token, PIN, IP privati, nomi di persone reali)
- [ ] `CHANGELOG.md` aggiornato sotto `[Non rilasciato]`
- [ ] Se la struttura cambia: `docs/ARCHITECTURE.md` aggiornato
- [ ] Se la scelta non e' ovvia: ADR aggiunto in `docs/adr/`

## Impatto sulla sicurezza

<!-- Obbligatorio se la PR tocca autenticazione, endpoint, segreti o
     comandi verso Home Assistant. Altrimenti scrivere "nessuno". -->
