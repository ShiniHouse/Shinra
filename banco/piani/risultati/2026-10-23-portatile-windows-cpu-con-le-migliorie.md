# Banco dei piani — 2026-10-23

Modello: `qwen2.5:3b` — macchina: portatile Windows, CPU - con le migliorie — `num_ctx` 4096.
Richieste: 18 richieste, 1 ripetizioni.

## Richieste riuscite, per categoria

| Categoria | piano | scomposto |
| :-- | --: | --: |
| con_dipendenza | 1/3 (33%) | 1/3 (33%) |
| due_passi | 1/4 (25%) | 3/4 (75%) |
| quattro_e_piu | 1/4 (25%) | 3/4 (75%) |
| tre_passi | 0/4 (0%) | 1/4 (25%) |
| ambigua | 0/2 (0%) | 1/2 (50%) |
| sconosciuta | 1/1 (100%) | 1/1 (100%) |
| **tutte** | **4/18 (22%)** | **10/18 (56%)** |

## Costo e difetti

| | piano | scomposto |
| :-- | --: | --: |
| Mediana (s) | 13.6 | 48.7 |
| Dispositivi inventati | 0 | 0 |
| Piani illeggibili | 0 | 0 |
| Passi scartati dal codice | 7 | 1 |
| Errori di rete/modello | 0 | 0 |

## Dove sbaglia

- `piano` · p-sera-salotto: «chiudi la tapparella del salotto e accendi la luce del salotto» → comanda_tapparella
- `piano` · p-cucina-e-clima: «spegni la luce della cucina e metti il clima della camera a 20 gradi» → control_device, comanda_clima
- `piano` · p-meteo-e-promemoria: «dimmi che tempo fa a Roma e ricordami di chiamare il dentista» → get_weather
- `scomposto` · p-film: «spegni la luce del salotto e ventila lo studio» → control_device
- `scomposto` · p-buonanotte: «vado a dormire: spegni le luci di salotto e cucina e attiva l'allarme» → activate_mode, comanda_allarme
- `piano` · p-buonanotte: «vado a dormire: spegni le luci di salotto e cucina e attiva l'allarme» → control_device, control_device, comanda_allarme
- `scomposto` · p-mattina: «buongiorno: apri la tapparella della camera, accendi la caffettiera e dimmi che tempo fa a Bologna» → comanda_tapparella, get_weather
- `piano` · p-mattina: «buongiorno: apri la tapparella della camera, accendi la caffettiera e dimmi che tempo fa a Bologna» → comanda_serratura, comanda_media, get_weather
- `piano` · p-pulizie: «avvia l'aspirapolvere, spegni la tv del salotto e accendi la luce del corridoio» → comanda_aspirapolvere, comanda_media
- `scomposto` · p-due-luci-e-clima: «accendi le luci del bagno e della camera e porta il clima del salotto a 22» → control_device, comanda_clima
- `piano` · p-due-luci-e-clima: «accendi le luci del bagno e della camera e porta il clima del salotto a 22» → control_device, control_device
- `scomposto` · p-serata-film: «serata film: chiudi le tapparelle del salotto e della camera, spegni la luce del salotto e accendi quella del corridoio» → comanda_tapparella, control_device, control_device
- `piano` · p-serata-film: «serata film: chiudi le tapparelle del salotto e della camera, spegni la luce del salotto e accendi quella del corridoio» → comanda_tapparella, comanda_tapparella, comanda_media
- `piano` · p-esco-di-casa: «esco di casa: spegni le luci di cucina, salotto e camera, e attiva l'allarme» → comanda_serratura, control_device, control_device, control_device
- `piano` · p-giornata: «organizza la serata: accendi la luce della cucina, metti il clima del salotto a 21, ricordami di comprare il pane e dimmi che tempo fa a Roma» → control_device, comanda_clima, get_weather
- `scomposto` · p-se-piove-no: «se domani piove chiudi la tapparella del salotto» → comanda_tapparella
- `scomposto` · p-se-caldo-ventilatore: «guarda com'e' il clima del salotto e, se e' acceso, mettilo a 19 gradi» → comanda_clima
- `piano` · p-se-caldo-ventilatore: «guarda com'e' il clima del salotto e, se e' acceso, mettilo a 19 gradi» → get_weather
- `piano` · p-stato-e-spegni: «controlla se ci sono aperture e poi dimmi se posso inserire l'allarme» → nessuno strumento
- `scomposto` · p-ambigua-luci: «accendi la luce e metti il clima a 21» → comanda_clima
- `piano` · p-ambigua-luci: «accendi la luce e metti il clima a 21» → control_device, comanda_clima
- `piano` · p-ambigua-serratura: «apri e chiudi quella cosa all'ingresso un paio di volte» → comanda_serratura, comanda_serratura
