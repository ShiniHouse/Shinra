---
title: "feat(casa): liste condivise, calendario e scadenze di manutenzione"
issue: 25
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Tre entita' semplici che poggiano tutte sul database della v0.2.0 e che oggi
mancano del tutto:

- **Liste condivise.** Nessuna lista della spesa o delle cose da fare, benche' il sistema conosca gia' i profili della famiglia.
- **Calendario.** Nessuna agenda: «cosa ho oggi» non ha risposta.
- **Manutenzione.** Nessuna scadenza: filtri della caldaia, revisione, bollo, garanzie.

## Cosa fare

- [x] Liste condivise con voci, autore, stato; aggiunta e lettura a voce.
      «Latte, pane e uova» sono tre voci, e una voce gia' presente non si
      aggiunge due volte: al supermercato due righe uguali si comprano due volte
- [x] Integrazione con le entita' `todo` dove presenti — e **delega, non copia.**
      Dove c'e' una lista `todo` si scrive li' e si legge di li'; le tabelle di
      casa restano vuote. Una copia sincronizzata sarebbe due verita' che
      divergono al primo conflitto, e una lista della spesa sbagliata e' peggio
      di nessuna lista
- [x] Calendario: lettura da tutte le entita' `calendar`, sommate agli eventi di
      casa. **Si leggono tutti, si scrive solo su quello di casa:** i calendari
      di Home Assistant sono di Google o iCloud, e una casa che scrive
      nell'agenda di lavoro di qualcuno fa un danno che non sa di fare
- [x] Scadenze ricorrenti con promemoria automatico. La prossima si conta **da
      quando e' stata fatta**, non dalla data prevista: altrimenti ogni ritardo
      si accumula e un cambio filtri fatto in ritardo tiene il calendario
      indietro per sempre
- [x] Documento collegato a una scadenza — **come riferimento, non come file.**
      Dove sta la garanzia, il numero della fattura, un percorso. Conservare gli
      allegati vuol dire caricamento, spazio disco e backup: e' una funzione sua,
      e prometterla qui con un campo di testo sarebbe peggio che non averla

## Criteri di accettazione

- [x] «Aggiungi il latte alla lista della spesa» funziona da chat e da Alexa
- [x] «Cosa ho oggi» elenca gli impegni reali, giornate intere comprese
- [x] Una scadenza di manutenzione genera un promemoria che scatta davvero — cosa
      che si e' potuta promettere solo dopo la riparazione dei promemoria (#92)

## Due cose che questa scheda ha fatto emergere

**I promemoria non suonavano.** Cercando dove agganciare le scadenze si e'
scoperto che il tool dei promemoria scriveva in una lista in memoria e
rispondeva «salvato» (issue #92, riparata prima di questa). Il criterio
«genera un promemoria che scatta davvero» non era realizzabile finche' quello
non era sistemato, ed e' il motivo per cui #92 e' venuta prima.

**«Cena» e' insieme un pasto e un'ora.** Un test del calendario ha mostrato
che «segna cena con Marco» diventava l'impegno «con Marco» alle venti: il
titolo mangiato dall'orario. Adesso la differenza la fa la preposizione —
«dopo cena» e' un'ora, «cena con Marco» e' un titolo.
