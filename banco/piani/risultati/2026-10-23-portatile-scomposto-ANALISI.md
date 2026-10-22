# Banco dei piani — la strategia «scomposto», primo giro (portatile, 2026-10-23)

Dati: [`2026-10-23-portatile-windows-cpu-scomposto.md`](2026-10-23-portatile-windows-cpu-scomposto.md) e il suo `.json`. Stesse 18 richieste, `qwen2.5:3b`,
`num_ctx` 4096, **un giro**, temperatura 0.1, **portatile** (non il server).

**L'idea da provare** (proposta del proprietario): non chiedere al modello di pianificare. Il **codice** spezza la frase in una cosa per pezzo (`spezza`), ogni
pezzo va al suo agente di dominio (il router sceglie, il modello vede 2-3 strumenti), il risultato passa dal validatore.

## I numeri

| | solo | agenti | piano | **scomposto** |
| :-- | --: | --: | --: | --: |
| Portatile (21/10 e 23/10) | 0/18 | 7/18 | 4/18 | **7/18** (39%) |
| Server (22/10) | 0/18 | 5/18 | 5/18 | *da misurare* |
| Mediana (portatile) | 58,7 s | 47,4 s | 10,6 s | 47,2 s |
| Dispositivi inventati | 17 | 1 | 0 | **0** |

Per categoria («scomposto», riuscite): due_passi 2/4, tre_passi 1/4, quattro_e_piu 1/4, con_dipendenza 1/3, ambigua 1/2, sconosciuta 1/1.

## Cosa dicono, senza esagerare

1. **Non c'è un vantaggio misurabile.** 7/18 è lo stesso numero degli agenti sul portatile, e il rumore fra due giri dello stesso modello è di una o due richieste su 18
   (vedi l'analisi del server). La scomposizione **non peggiora** e **non inventa niente** (0 dispositivi inventati, un solo passo scartato), ma **non migliora** in modo che
   si possa dichiarare. Un risultato così non basta a costruirci sopra.
2. **I passi giusti sono 9 su 18, gli argomenti completi 5.** Delle due richieste dove gli strumenti erano quelli giusti e il verdetto dice «sbagliata», **in entrambe il
   modello ha dimenticato un parametro obbligatorio**: ha chiamato `comanda_clima` con la temperatura e **senza `azione`** («metti il clima della camera a 20 gradi»,
   «metti il clima del salotto a 21»). Non è un difetto della scomposizione: è il modello piccolo che non compila lo schema. È un errore che **il codice può vedere**: i
   parametri obbligatori sono nello schema dello strumento, e un passo senza i suoi obbligatori non si esegue (non ho verificato cosa fa oggi lo strumento con un obbligatorio mancante).
3. **Il taglio fa quello che deve dove c'è da tagliare**: «chiudi la tapparella e accendi la luce», «dimmi che tempo fa e ricordami di...», «spegni la cucina e metti il clima»
   arrivano a due pezzi giusti. Dove la frase non si taglia bene, si vede: «ventila lo studio» non ha una parola d'azione nel lessico (`ventil` manca) e resta attaccato al pezzo
   prima; «accendi quella del corridoio» perde la parola «luce». Sono limiti del **lessico**, non del metodo, e si correggono nel file della lingua.
4. **Il «se... poi...» resta fuori portata**: `con_dipendenza` 1/3, come le altre strategie. Spezzare non aiuta quando il secondo pezzo dipende dal risultato del primo.

## Cosa ne segue

- **Da solo, non cambia la risposta sulla 0.9.0**: nessuna strategia con questo modello supera il 40%, e le differenze sono dentro il rumore. Il multi-agente (#432) resta non costruito.
- **La scomposizione è però la forma giusta del pezzo che manca davvero**: un taglio deterministico, senza modello, con l'agente di dominio e il validatore. Costa lo stesso tempo degli agenti
  (47 s: un giro di modello per pezzo) ma **non ha nessuna invenzione** e ogni pezzo è piccolo. Se la #191 (piani) si costruisce, questa è un'alternativa al «piano scritto dal modello».
- **Due migliorie senza modello, da misurare**: (a) controllare i **parametri obbligatori** di ogni passo (e dire cosa manca, senza eseguire); (b) allargare il lessico delle parole d'azione
  (`ventil`, `luce` nei pezzi che dicono «quella») nel file della lingua. Poi rimisurare con più ripetizioni.
- **Per decidere serve il server**, con più ripetizioni: `python scripts/banco_piani.py --strategie scomposto agenti piano --ripetizioni 2 --macchina "i5-8500T, 16 GB, niente GPU" --senza-file`
  (circa un'ora e mezza; di notte).
