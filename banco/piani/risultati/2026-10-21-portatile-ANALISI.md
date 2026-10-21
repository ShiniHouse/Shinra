# Banco dei piani — primo giro, cosa dicono i numeri (2026-10-21)

Dati: [`2026-10-21-portatile-windows-cpu-senza-server.md`](2026-10-21-portatile-windows-cpu-senza-server.md) e il suo `.json`.
18 richieste a più passi (`banco/piani/corpus.yaml`), modello `qwen2.5:3b`, `num_ctx` 4096, **un solo giro** a temperatura 0.1.

## Cosa NON dicono (prima di tutto)

- **È un portatile Windows, non l'i5-8500T di casa.** Le *percentuali* dipendono poco dalla macchina, i *tempi* per niente: vanno rifatti sul server
  (`python scripts/banco_piani.py --macchina "i5-8500T, 16 GB, niente GPU"`).
- **Un giro, 18 richieste**: ogni richiesta vale cinque punti percentuali. Una differenza di una o due richieste fra strategie **non** è una differenza.
  Per un numero su cui decidere servono più ripetizioni (`--ripetizioni 3`) e il server.
- Il verdetto è severo di proposito: una richiesta riesce solo se gli strumenti sono **esattamente** quelli giusti, gli argomenti anche, e non c'è niente di
  inventato. «Quasi giusto» vale zero.

## Cosa dicono

| | solo | agenti | piano |
| :-- | --: | --: | --: |
| Riuscite | **0/18** | **7/18** (39%) | **4/18** (22%) |
| Strumenti giusti (anche con argomenti sbagliati) | 0 | 10 | 8 |
| Mediana | 58,7 s | 47,4 s | **10,6 s** |
| Dispositivi inventati | 17 | 1 | 0 |

1. **Il ciclo «solo» non è un campione neutro: è il difetto già noto dell'ADR 0008.** In tutte le 18 richieste Ollama ha letto 2.050 token di un prompt
   che ne pesa quasi il triplo: il catalogo intero (36 strumenti) **non ci sta in 4.096 di contesto** e il modello sceglie fra strumenti che non ha visto
   (accende le luci con `comanda_tapparella`, 17 dispositivi inventati). Non dice che il modello non sa pianificare: dice che con tutto il catalogo davanti non
   riesce nemmeno a scegliere. Il router per dominio (`agenti`, ADR 0008) è quello che lo risolve, e infatti passa da 0 a 7.
2. **Il piano scritto in anticipo è il più veloce (10 s contro 47–59) e non inventa dispositivi** (il codice ne ha scartati 3: è il controllo che la #191 chiede),
   **ma sbaglia di più su cosa fare**: 4 su 18 contro 7. Gli errori tipici: aggiunge passi mai chiesti (`p-mattina`: sei passi per tre richieste, con una
   serratura e un clima che nessuno aveva nominato), confonde il dominio, e su una richiesta ambigua pianifica comunque.
3. **Il «leggere prima, poi decidere» è il punto dolente di tutti**: `con_dipendenza` fa 0/3, 1/3, 1/3. Con «se domani piove chiudi la tapparella» sia `solo`
   sia `agenti` chiudono la tapparella **senza guardare il tempo** (in casa finta è sereno): è esattamente l'errore che un piano in anticipo non può evitare e che
   un agente che rilegge il risultato dovrebbe poter evitare, ma questo modello non lo fa da solo.
4. **Le richieste da fermare** (ambigue o su ciò che la casa non ha) sono quasi tutte sbagliate: il modello comanda comunque. Qui la rete di sicurezza non è il
   modello ma il codice (la conferma, #192, e la validazione dei dispositivi).

## Cosa ne segue per la 0.9.0

- **Il multi-agente (#432) non è dimostrato**: nessuna strategia arriva a una percentuale su cui si possa costruire (39% al massimo). Con un modello da 3 miliardi
  di parametri l'orchestratore e il revisore moltiplicano i passi di un modello che sbaglia circa una volta su due. **Non si costruisce finché il banco, rifatto sul
  server e con più ripetizioni, non mostra un vantaggio chiaro** (o finché un modello più capace, locale o esterno, non lo mostra). È la regola scritta nell'ADR 0013.
- **Il validatore dei piani vale già**: scartare i passi con strumenti o dispositivi inesistenti toglie le invenzioni (17 → 0). È la parte della #191 che si può
  costruire subito, qualunque strategia vinca.
- **Il passo successivo più utile è misurare, non costruire**: lo stesso banco con un modello più grande (`qwen2.5:7b` se la macchina lo regge, e quello esterno quando
  ci sarà la #194) e con il router per dominio **davanti al piano**; poi `--ripetizioni 3` sul server. Il banco è pronto per tutte e tre.
- **«Ci penso» (#431) non dipende da questi numeri**: la coda dei lavori serve comunque, perché con 47–59 secondi a richiesta (e 130 sul server, ADR 0008) le richieste
  lente esistono già oggi.
