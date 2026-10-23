# Banco dei piani — «scomposto» con le due migliorie senza modello (portatile, 2026-10-23)

Dati: [`2026-10-23-portatile-windows-cpu-con-le-migliorie.md`](2026-10-23-portatile-windows-cpu-con-le-migliorie.md) e il suo `.json`. Stesse 18 richieste, `qwen2.5:3b`, `num_ctx` 4096,
**un giro**, portatile. Segue [`2026-10-23-portatile-scomposto-ANALISI.md`](2026-10-23-portatile-scomposto-ANALISI.md).

Le due migliorie, entrambe **codice, senza modello**:

1. **Parametri obbligatori** (`completa_argomenti`): se manca un obbligatorio che è una scelta fra valori e **uno solo** dei valori è anche il nome di un altro argomento presente, lo si completa
   (`temperatura: 20` → `azione: temperatura`); altrimenti il passo si scarta dicendo cosa manca. Non indovina mai fra due.
2. **Lessico**: «ventil» diventa parola d'azione, e «quella/quello» prende il nome dell'ultimo dispositivo detto («accendi quella del corridoio» → «accendi la luce del corridoio»).

## I numeri

| Riuscite | prima (7/18 su `scomposto`, 4/18 su `piano`) | con le migliorie |
| :-- | --: | --: |
| **scomposto** | 7/18 (39%) | **10/18 (56%)** |
| piano | 4/18 (22%) | 4/18 (22%) |
| Strumenti giusti (scomposto) | 9/18 | 10/18 |
| Argomenti completi (scomposto) | 5/18 | 8/18 |
| Dispositivi inventati | 0 | 0 |
| Mediana (scomposto) | 47,2 s | 48,7 s |

Richieste che cambiano esito in `scomposto`: `p-cucina-e-clima` e `p-giornata` (sbagliate → giuste), `p-tutte-le-luci` (sbagliata → giusta).

## Cosa dicono, senza esagerare

1. **Due delle tre richieste guadagnate sono merito del codice, la terza no.** `p-cucina-e-clima` e `p-giornata` avevano gli strumenti giusti ma `comanda_clima` senza `azione`: la
   completazione lo ripara (è deterministico e si vede nel dettaglio). `p-tutte-le-luci` non c'entra: prima il modello aveva chiamato tre luci su quattro, stavolta quattro su quattro,
   a parità di codice per quel caso. È **rumore**. L'effetto attribuibile è quindi **circa +2 richieste su 18** (7 → 9, circa 50%), non +3.
2. **Il lessico non ha prodotto una richiesta in piu'**: `p-film` («ventila lo studio») resta sbagliata anche se ora il pezzo esiste, perche' davanti a «ventila lo studio» il modello
   **non produce nessuna chiamata** (il validatore non ha scartato niente: non c'era niente da scartare). E' un errore del modello, non di taglio. Il pronome non ha cambiato nessun
   verdetto in questo giro.
3. **Il piano scritto dal modello non beneficia**: 4/18 come prima, 7 passi scartati. Il suo problema non è l'argomento mancante ma i passi sbagliati o aggiunti.
4. **Resta una sola strategia senza invenzioni e con un guadagno ripetibile**: scomposto + validatore con completamento. Costa quanto gli agenti (circa 48 s: un giro per pezzo).

## Cosa ne segue

- **Il risultato è il migliore dei quattro giri su portatile, ma è ancora una misura sola** (18 richieste, un giro). Per dichiararlo serve il server e più ripetizioni:
  `.venv/bin/python -u scripts/banco_piani.py --strategie scomposto agenti piano --ripetizioni 2 --macchina "i5-8500T, 16 GB, niente GPU" --senza-file`.
- **Cosa si può dire già**: il **validatore con completamento dei parametri obbligatori** è un miglioramento meccanico e sicuro (non indovina mai fra due scelte), indipendente dalla strategia, e vale la
  pena di costruirlo nella #191 qualunque forma abbia il piano. Il **multi-agente (#432) resta non costruito**: nessun dato lo giustifica.
- **Un limite da dichiarare**: la completazione ripara **un** tipo di errore del modello (parametro obbligatorio dimenticato ma deducibile). Gli altri (strumento sbagliato, passo mai chiesto,
  nessuna chiamata per «ventila lo studio») restano, e per questi servono un modello più capace o un controllo semantico che qui non c'è.
