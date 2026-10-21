# Banco dei piani — 2026-10-21

Modello: `qwen2.5:3b` — macchina: portatile Windows, CPU, senza server — `num_ctx` 4096.
Richieste: 18 richieste, 1 ripetizioni.

## Richieste riuscite, per categoria

| Categoria | solo | agenti | piano |
| :-- | --: | --: | --: |
| con_dipendenza | 0/3 (0%) | 1/3 (33%) | 1/3 (33%) |
| due_passi | 0/4 (0%) | 2/4 (50%) | 1/4 (25%) |
| quattro_e_piu | 0/4 (0%) | 2/4 (50%) | 1/4 (25%) |
| tre_passi | 0/4 (0%) | 1/4 (25%) | 0/4 (0%) |
| ambigua | 0/2 (0%) | 1/2 (50%) | 0/2 (0%) |
| sconosciuta | 0/1 (0%) | 0/1 (0%) | 1/1 (100%) |
| **tutte** | **0/18 (0%)** | **7/18 (39%)** | **4/18 (22%)** |

## Costo e difetti

| | solo | agenti | piano |
| :-- | --: | --: | --: |
| Mediana (s) | 58.7 | 47.4 | 10.6 |
| Dispositivi inventati | 17 | 1 | 0 |
| Piani illeggibili | 0 | 0 | 0 |
| Passi scartati dal codice | 0 | 0 | 3 |
| Errori di rete/modello | 0 | 0 | 0 |

## Dove sbaglia

- `solo` · p-sera-salotto: «chiudi la tapparella del salotto e accendi la luce del salotto» → comanda_tapparella
- `piano` · p-sera-salotto: «chiudi la tapparella del salotto e accendi la luce del salotto» → comanda_tapparella
- `solo` · p-cucina-e-clima: «spegni la luce della cucina e metti il clima della camera a 20 gradi» → comanda_tapparella, stato_clima, comanda_tapparella
- `agenti` · p-cucina-e-clima: «spegni la luce della cucina e metti il clima della camera a 20 gradi» → control_device, comanda_clima
- `piano` · p-cucina-e-clima: «spegni la luce della cucina e metti il clima della camera a 20 gradi» → control_device, comanda_clima
- `solo` · p-meteo-e-promemoria: «dimmi che tempo fa a Roma e ricordami di chiamare il dentista» → quali_liste, aggiungi_impegno
- `piano` · p-meteo-e-promemoria: «dimmi che tempo fa a Roma e ricordami di chiamare il dentista» → get_weather
- `solo` · p-film: «spegni la luce del salotto e ventila lo studio» → comanda_tapparella, comanda_tapparella
- `agenti` · p-film: «spegni la luce del salotto e ventila lo studio» → control_device, control_device
- `solo` · p-buonanotte: «vado a dormire: spegni le luci di salotto e cucina e attiva l'allarme» → togli_da_lista, togli_da_lista, aggiungi_impegno
- `agenti` · p-buonanotte: «vado a dormire: spegni le luci di salotto e cucina e attiva l'allarme» → activate_mode
- `piano` · p-buonanotte: «vado a dormire: spegni le luci di salotto e cucina e attiva l'allarme» → control_device, control_device, comanda_allarme
- `solo` · p-mattina: «buongiorno: apri la tapparella della camera, accendi la caffettiera e dimmi che tempo fa a Bologna» → aggiungi_a_lista, aggiungi_a_lista, stato_clima
- `agenti` · p-mattina: «buongiorno: apri la tapparella della camera, accendi la caffettiera e dimmi che tempo fa a Bologna» → comanda_tapparella
- `piano` · p-mattina: «buongiorno: apri la tapparella della camera, accendi la caffettiera e dimmi che tempo fa a Bologna» → get_home_status, get_home_status, comanda_tapparella, comanda_serratura, comanda_media, comanda_clima
- `solo` · p-pulizie: «avvia l'aspirapolvere, spegni la tv del salotto e accendi la luce del corridoio» → comanda_tapparella, comanda_tapparella, comanda_tapparella
- `piano` · p-pulizie: «avvia l'aspirapolvere, spegni la tv del salotto e accendi la luce del corridoio» → comanda_aspirapolvere, comanda_media, control_device
- `solo` · p-due-luci-e-clima: «accendi le luci del bagno e della camera e porta il clima del salotto a 22» → comanda_tapparella, comanda_tapparella, stato_clima
- `agenti` · p-due-luci-e-clima: «accendi le luci del bagno e della camera e porta il clima del salotto a 22» → control_device, control_device, comanda_clima
- `piano` · p-due-luci-e-clima: «accendi le luci del bagno e della camera e porta il clima del salotto a 22» → control_device, control_device, comanda_clima
- `solo` · p-serata-film: «serata film: chiudi le tapparelle del salotto e della camera, spegni la luce del salotto e accendi quella del corridoio» → comanda_tapparella, comanda_tapparella, stato_clima, stato_tapparella
- `piano` · p-serata-film: «serata film: chiudi le tapparelle del salotto e della camera, spegni la luce del salotto e accendi quella del corridoio» → comanda_tapparella, comanda_tapparella, comanda_media, control_device
- `solo` · p-esco-di-casa: «esco di casa: spegni le luci di cucina, salotto e camera, e attiva l'allarme» → togli_da_lista, aggiungi_a_lista, stato_clima
- `agenti` · p-esco-di-casa: «esco di casa: spegni le luci di cucina, salotto e camera, e attiva l'allarme» → control_device, control_device, control_device, comanda_allarme
- `piano` · p-esco-di-casa: «esco di casa: spegni le luci di cucina, salotto e camera, e attiva l'allarme» → comanda_serratura, control_device, control_device, control_device, comanda_allarme
- `solo` · p-giornata: «organizza la serata: accendi la luce della cucina, metti il clima del salotto a 21, ricordami di comprare il pane e dimmi che tempo fa a Roma» → aggiungi_impegno, aggiungi_a_lista, stato_clima
- `agenti` · p-giornata: «organizza la serata: accendi la luce della cucina, metti il clima del salotto a 21, ricordami di comprare il pane e dimmi che tempo fa a Roma» → control_device, control_device
- `piano` · p-giornata: «organizza la serata: accendi la luce della cucina, metti il clima del salotto a 21, ricordami di comprare il pane e dimmi che tempo fa a Roma» → control_device, comanda_clima, get_weather
- `solo` · p-tutte-le-luci: «spegni le luci della cucina, del salotto, della camera e dello studio» → comanda_tapparella, comanda_tapparella, comanda_tapparella
- `solo` · p-se-piove-no: «se domani piove chiudi la tapparella del salotto» → comanda_tapparella
- `agenti` · p-se-piove-no: «se domani piove chiudi la tapparella del salotto» → comanda_tapparella
- `solo` · p-se-caldo-ventilatore: «guarda com'e' il clima del salotto e, se e' acceso, mettilo a 19 gradi» → stato_clima
- `agenti` · p-se-caldo-ventilatore: «guarda com'e' il clima del salotto e, se e' acceso, mettilo a 19 gradi» → comanda_clima
- `piano` · p-se-caldo-ventilatore: «guarda com'e' il clima del salotto e, se e' acceso, mettilo a 19 gradi» → get_weather
- `solo` · p-stato-e-spegni: «controlla se ci sono aperture e poi dimmi se posso inserire l'allarme» → quali_liste
- `piano` · p-stato-e-spegni: «controlla se ci sono aperture e poi dimmi se posso inserire l'allarme» → nessuno strumento
- `solo` · p-ambigua-luci: «accendi la luce e metti il clima a 21» → comanda_tapparella, stato_clima
- `agenti` · p-ambigua-luci: «accendi la luce e metti il clima a 21» → control_device, comanda_clima
- `piano` · p-ambigua-luci: «accendi la luce e metti il clima a 21» → control_device, comanda_clima
- `solo` · p-ambigua-serratura: «apri e chiudi quella cosa all'ingresso un paio di volte» → comanda_tapparella, comanda_tapparella
- `piano` · p-ambigua-serratura: «apri e chiudi quella cosa all'ingresso un paio di volte» → comanda_serratura, comanda_serratura
- `solo` · p-sconosciuta-garage: «alza la basculante del garage e accendi la luce del garage» → comanda_tapparella, aggiungi_a_lista
- `agenti` · p-sconosciuta-garage: «alza la basculante del garage e accendi la luce del garage» → control_device
