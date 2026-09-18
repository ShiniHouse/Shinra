#!/bin/sh
# Quello che va fatto una volta sola, prima di far partire il servizio.
#
# Sta in uno script e non nel `CMD` perche' deve girare anche quando qualcuno
# entra nel contenitore per lanciare un comando diverso — per esempio
# `scripts/salvataggio.py` — e si aspetta di trovare la casa in ordine.
set -e

# Il file di esempio nell'immagine sta fuori dal volume apposta (vedi il
# Dockerfile). Se la configurazione e' vuota — primo avvio, volume nuovo — ce
# lo si mette, cosi' chi apre quella cartella trova il riferimento commentato
# invece del nulla.
if [ ! -f /app/config/config.example.yaml ]; then
    cp /opt/shinra/config.example.yaml /app/config/config.example.yaml
fi

# `config.yaml` **non** si crea: l'applicazione, se non lo trova, legge
# l'esempio. Crearlo vorrebbe dire che ogni aggiornamento dell'esempio
# smette di arrivare a chi non l'ha mai toccato.

# Gli esempi da cui nasce la prima casa. `assicura_dati_iniziali()` li cerca
# in `data/examples/` e da li' crea il profilo amministratore: senza, non
# c'e' nessun utente, il PIN del primo accesso non viene generato, e la
# dashboard resta chiusa per sempre — con l'applicazione che risponde 200 e
# sembra a posto.
if [ ! -d /app/data/examples ]; then
    mkdir -p /app/data/examples
    cp /opt/shinra/esempi/* /app/data/examples/
fi

exec "$@"
