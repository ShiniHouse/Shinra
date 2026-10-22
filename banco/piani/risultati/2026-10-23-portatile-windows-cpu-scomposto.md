# Banco dei piani — 2026-10-23

Modello: `qwen2.5:3b` — macchina: portatile Windows, CPU - scomposto — `num_ctx` 4096.
Richieste: 18 richieste, 1 ripetizioni.

## Richieste riuscite, per categoria

| Categoria | scomposto |
| :-- | --: |
| con_dipendenza | 1/3 (33%) |
| due_passi | 2/4 (50%) |
| quattro_e_piu | 1/4 (25%) |
| tre_passi | 1/4 (25%) |
| ambigua | 1/2 (50%) |
| sconosciuta | 1/1 (100%) |
| **tutte** | **7/18 (39%)** |

## Costo e difetti

| | scomposto |
| :-- | --: |
| Mediana (s) | 47.2 |
| Dispositivi inventati | 0 |
| Piani illeggibili | 0 |
| Passi scartati dal codice | 1 |
| Errori di rete/modello | 0 |

## Dove sbaglia

- `scomposto` · p-cucina-e-clima: «spegni la luce della cucina e metti il clima della camera a 20 gradi» → control_device, comanda_clima
- `scomposto` · p-film: «spegni la luce del salotto e ventila lo studio» → control_device, control_device
- `scomposto` · p-buonanotte: «vado a dormire: spegni le luci di salotto e cucina e attiva l'allarme» → activate_mode, comanda_allarme
- `scomposto` · p-mattina: «buongiorno: apri la tapparella della camera, accendi la caffettiera e dimmi che tempo fa a Bologna» → comanda_tapparella, get_weather
- `scomposto` · p-due-luci-e-clima: «accendi le luci del bagno e della camera e porta il clima del salotto a 22» → control_device, comanda_clima
- `scomposto` · p-serata-film: «serata film: chiudi le tapparelle del salotto e della camera, spegni la luce del salotto e accendi quella del corridoio» → comanda_tapparella, control_device, control_device
- `scomposto` · p-giornata: «organizza la serata: accendi la luce della cucina, metti il clima del salotto a 21, ricordami di comprare il pane e dimmi che tempo fa a Roma» → control_device, comanda_clima, add_reminder, get_weather
- `scomposto` · p-tutte-le-luci: «spegni le luci della cucina, del salotto, della camera e dello studio» → control_device, control_device, control_device
- `scomposto` · p-se-piove-no: «se domani piove chiudi la tapparella del salotto» → comanda_tapparella
- `scomposto` · p-se-caldo-ventilatore: «guarda com'e' il clima del salotto e, se e' acceso, mettilo a 19 gradi» → comanda_clima
- `scomposto` · p-ambigua-luci: «accendi la luce e metti il clima a 21» → control_device, comanda_clima
