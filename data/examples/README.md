# Dati di esempio

Questi file sono i **valori iniziali** distribuiti con il progetto, non lo
stato di una casa reale. Sono versionati e possono essere modificati con una
Pull Request come qualsiasi altro file del repository.

Al primo avvio, ogni file mancante in `data/` viene creato copiando l'esempio
corrispondente. Da quel momento la copia in `data/` appartiene
all'installazione: contiene i nomi della famiglia, le abitudini della casa,
gli alias dei dispositivi reali. Per questo `data/*.json` non e' versionato.

Non modificare `data/examples/` per configurare la propria casa: si modifica
`data/`, oppure — meglio — l'interfaccia web.
