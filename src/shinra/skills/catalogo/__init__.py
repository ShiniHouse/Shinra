"""Gli strumenti che il modello puo' chiamare, un modulo per dominio.

Ogni modulo dichiara due cose: `GESTORI` (nome dello strumento -> funzione) e
`SCHEMI` (la descrizione che il modello legge per decidere quando chiamarlo).
`skills/registry.py` li mette insieme. Aggiungere uno strumento vuol dire
toccare il modulo del suo dominio, non un file di ottocento righe; e il giorno
che gli agenti di dominio (#190) vorranno vedere solo i propri strumenti, la
divisione e' gia' fatta.
"""
