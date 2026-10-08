# Plugin

Un plugin aggiunge a Shinra uno o più strumenti senza modificare il suo codice: una cartella in `plugins/` con un
**manifesto** che dice cosa fa e di cosa ha bisogno, e un modulo che lo realizza. Questa guida dice come è fatto,
cosa garantisce e, soprattutto, **cosa non garantisce**.

> **In questa fase i plugin sono solo tuoi.** Girano dentro il processo di Shinra, e caricare codice scritto da altri
> dentro il processo che comanda la casa è la peggior superficie d'attacco possibile. I plugin di terzi richiedono un
> processo separato e sono un'altra decisione ([#193](storia-delle-fasi.md), 2026-10-08). Il manifesto con
> `"origine"` diversa da `"proprio"` si rifiuta.

## 1. Cosa garantisce

- **Un plugin non abilitato non si importa nemmeno.** Si abilita nominandolo in `config/config.yaml`:

  ```yaml
  plugin:
    abilitati: [esempio_dado]
  ```

  Per difetto non ce n'è nessuno. Il cambio vale al riavvio.
- **Un permesso non dichiarato non si concede.** Il plugin agisce sulla casa tramite il `Contesto` che riceve, e il
  `Contesto` controlla ogni richiesta contro il manifesto (vedi sotto).
- **Serrature, allarme e script non si possono dichiarare.** Un manifesto che li chiede non è valido.
- **Un plugin rotto non ferma il servizio.** Se non si carica finisce nel log con il motivo; se solleva
  un'eccezione mentre lavora, la risposta è un errore leggibile e il resto funziona.
- **Il registro delle azioni dice quale plugin ha fatto cosa**: ogni voce `tool.<strumento>` ha il campo `plugin`.
- **Un plugin che comanda dispositivi chiede conferma.** Uno strumento sconosciuto è «sensibile» per difetto
  ([CONFERME.md](CONFERME.md)); un plugin che dichiara `domini_ha` lo resta, e ogni uso chiede il «sì». Un plugin senza
  nessun permesso sulla casa (come il dado) parte direttamente.

## 2. Cosa NON garantisce

Un plugin è codice Python **nello stesso processo** di Shinra. Se il suo codice vuole aggirare il `Contesto` — importare
`httpx` e chiamare un indirizzo qualsiasi, leggere un file — **può**: nessun meccanismo lo impedisce. I permessi sono un
**patto verificabile** fra chi scrive il plugin e chi lo abilita, non una prigione. Per questo si leggono prima di
abilitare, e per questo il codice di terzi non si carica.

## 3. Com'è fatto

```
plugins/
  esempio_dado/
    plugin.json     # il manifesto
    plugin.py       # SCHEMI e GESTORI
```

Il manifesto (`plugin.json`):

```json
{
  "nome": "esempio_dado",
  "versione": "1.0.0",
  "descrizione": "Tira un dado: un plugin di esempio, senza nessun permesso.",
  "strumenti": ["esempio_dado_tira"],
  "parole": ["tira un dado", "lancia un dado"],
  "permessi": {}
}
```

| Campo | Cosa è |
| :--- | :--- |
| `nome` | Come la cartella: minuscolo, lettere, cifre e `_` |
| `strumenti` | Gli strumenti che il modello vede. Ognuno si chiama `<nome>_…`, così i nomi non si confondono con quelli di Shinra |
| `parole` | Le parole con cui il router sceglie questo plugin (come per gli [agenti](AGENTI.md)): ogni plugin è un agente, e il modello vede solo i suoi strumenti |
| `permessi.domini_ha` | I tipi di dispositivo che può comandare (`light`, `switch`, `cover`, …). Mai `lock`, `alarm_control_panel`, `script` |
| `permessi.rete` | Gli host che può raggiungere, solo nomi (`api.esempio.it`, senza `https://` né porte) |
| `permessi.conoscenza` | `true` se può leggere la conoscenza della casa |

Il modulo (`plugin.py`) espone `SCHEMI` (gli schemi degli strumenti, come per gli strumenti di Shinra) e `GESTORI`
(nome → funzione). **Gli strumenti del modulo devono essere esattamente quelli del manifesto.** Ogni funzione riceve il
`Contesto` come primo argomento, poi gli argomenti del modello:

```python
async def accendi(contesto, entity_id: str):
    return await contesto.comanda(entity_id, "turn_on")   # solo domini dichiarati
```

Il `Contesto` offre tre cose, e ognuna controlla il manifesto:

- `comanda(entity_id, servizio, dati=None)`: solo un dominio dichiarato, mai una cosa delicata (un garage, anche se è una
  `cover`), e passa dal motore di Shinra che verifica che il dispositivo esista;
- `leggi(url)`: solo da un host dichiarato;
- `conoscenza()`: solo con il permesso `conoscenza`.

Un permesso negato solleva `PermessoPluginNegato` con una frase che dice cosa mancava.

## 4. Provarlo

Il plugin `esempio_dado` è nel repository. Abilitalo, riavvia, e dalla chat scrivi «tira un dado»: deve rispondere con un
numero, e nel registro (`scripts/registro.py --azione tool.esempio_dado_tira`) compare la voce con `plugin:
esempio_dado`. Se non parte, il motivo è nel log: `journalctl -u shinra | grep Plugin`.
