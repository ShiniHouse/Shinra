# Una voce che parla dal server (Piper)

Le voci di rete (Diego, Elsa, …) passano da internet: se la rete e' lenta l'audio arriva a pezzi, e ogni frase che Shinra dice
esce di casa. **Piper** e' una voce neurale che gira sul server: niente rete, niente testo fuori, nessun costo.

E' facoltativa. Senza, tutto resta com'era; con una voce messa in casa compare nell'elenco delle voci in Impostazioni
(«🏠 … (locale)»). Se una voce locale non si puo' usare (file spariti, errore), Shinra ripiega su Diego e lo scrive nel log:
non resta muta.

## Installarla sul server

Da fare una volta, sul server, con l'ambiente di Shinra (`/opt/Shinra/.venv`):

```bash
cd /opt/Shinra
.venv/bin/pip install -e ".[voce-locale]"
mkdir -p data/voci
.venv/bin/python -m piper.download_voices --data-dir data/voci it_IT-paola-medium
sudo systemctl restart shinra
```

`it_IT-paola-medium` e' la voce italiana di qualita' media (circa 60 MB). Ce n'e' anche una piu' leggera,
`it_IT-riccardo-x_low` (circa 25 MB, maschile, qualita' piu' bassa). L'elenco di tutte e' su
<https://huggingface.co/rhasspy/piper-voices>. Una voce e' una coppia di file in `data/voci/`: `nome.onnx` e `nome.onnx.json`.
La cartella si cambia con `voce.cartella_voci` in `config.yaml`.

Poi, in Impostazioni → Voce, scegli la voce locale e premi la prova.

## Cosa aspettarsi

- **La prima frase dopo l'avvio e' piu' lenta** (qualche secondo): la voce si carica dal disco una volta, poi resta in memoria.
- **La velocita'** del cursore vale; **il tono no** (Piper non lo cambia): quel cursore resta per le voci di rete e del browser.
- Misurato su un PC da scrivania: circa 0,1 secondi di calcolo per ogni secondo di audio. **Sul server (i5-8500T, senza GPU) non
  e' ancora misurato**: se e' lento, la voce `x_low` e' la strada.
- Una frase alla volta: le richieste di voce si mettono in fila, cosi' la CPU resta anche per il modello e per Home Assistant.
