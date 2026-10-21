# 0013 — Agenti e modelli che imparano: propongono, non decidono

- **Stato:** Accettato
- **Data:** 2026-10-21 (accettato dal proprietario lo stesso giorno)
- **Attuazione:** milestone `v0.9.0`, issue #191, #194, #240 e #430–#438 (proposta in [`docs/proposte/agenti-0.9.0/`](../proposte/agenti-0.9.0/README.md))

## Contesto

Il proprietario vuole che più agenti e più modelli lavorino dentro Shinra, imparino dalle istruzioni e si sistemino da soli per rispondere alle
esigenze della famiglia, e che Shinra si prenda il tempo che serve per le richieste difficili. Tre scelte sono già state fatte
(2026-10-21) e questo ADR le fissa, con le regole che le rendono sicure.

Cosa pesa:

- La casa è **vera**: luci, riscaldamento, serrature. Un errore di un modello da 3 miliardi di parametri (misurato: sceglie lo strumento giusto
  nel ~73% dei casi a contesto pieno, ADR 0008) costa più di quanto si guadagna.
- Il server è un i5-8500T **senza GPU**: più modelli e più passi competono per la stessa CPU con la chat e con Home Assistant.
- La promessa del README è «resta tutto in casa». Un modello esterno la cambia, e deve cambiarla **in chiaro**.

## Decisione

1. **Impara proponendo, non decidendo.** Il ciclo è osserva → ipotizza → prova a secco → misura sul banco → **propone** → conferma di una persona →
   applica → si può annullare. Shinra **non applica da sola**: nessuna correzione, nessuna routine, nessuna regola. Una proposta in attesa
   non cambia il comportamento. Il cancello è il banco: una correzione che peggiora una misura non si propone.
2. **Cosa può proporre** (elenco chiuso): alias e sinonimi, parole di un dominio, domande dell'intervista, ricordi, routine e regole **spente**.
   **Cosa non può mai:** modificare codice, permessi, ruoli, configurazione, azioni su serrature, allarme o garage; attivare niente; cambiare i
   pesi di un modello. Impara cambiando **dati e istruzioni** che si vedono e si annullano.
3. **I modelli si configurano per scopo** (`chat`, `pianifica`, `riassumi`, `embedding`), ognuno `locale`, `rete` (un'altra macchina di casa) o
   `esterno`. Un modello che non risponde non ferma la casa: gli intenti deterministici funzionano, il resto dice cosa manca.
4. **Un modello esterno è facoltativo, spento di default, e per scopo.** Si attiva con un consenso che dice **cosa esce, verso chi e quando**, è
   revocabile, e c'è sempre il ripiego locale. **Esce solo:** il testo della richiesta, gli strumenti rilevanti e i risultati che servono al
   compito. **Non esce mai:** ricordi privati, segreti e chiavi, coordinate, la memoria intera, il testo di una conversazione di un altro
   profilo. La chiave sta in `.env`, mai in `config.yaml` né nel registro. Ogni richiesta esterna è nel registro (scopo, dimensione, momento),
   **mai** il contenuto.
5. **Una richiesta lunga diventa un lavoro.** Shinra risponde subito «ci sto lavorando», il lavoro ha un proprietario, uno scopo, un tetto di tempo e
   di passi, uno stato e un avanzamento, sopravvive a un riavvio, si può annullare e consegna l'esito. I lavori pesanti hanno **concorrenza uno** e priorità
   bassa. I lavori privati sono visibili solo a chi li ha chiesti.
6. **Più agenti con confini nell'esecuzione.** Ogni agente ha solo i suoi strumenti, e il confine sta nel codice che esegue, non nel prompt (come nell'ADR
   0008). I messaggi fra agenti sono tracciati. Un piano si **valida** prima di eseguirlo e si **verifica** dopo ogni passo; ogni richiesta ha un tetto di passi,
   di tempo e di costo.
7. **Il contenuto che arriva da fuori è dato, non istruzione.** Pagine web, notizie, risposte di un modello esterno non possono far eseguire azioni:
   le azioni sensibili passano **sempre** dalla conferma (#192), e un corpus di tentativi di iniezione non deve produrre nessuna azione.
8. **Un interruttore generale.** Un solo comando spegne i lavori, i modelli esterni e l'imparare, e la casa torna a funzionare come nella `0.8.0`.

## Alternative scartate

- *Autonomia su cose reversibili* (applicare da sola un alias o un sinonimo e avvisare dopo): più comoda, ma richiede già un registro e un annulla
  provati. Si può arrivarci **per gradi** con un nuovo ADR, dopo mesi di misure; non è il punto di partenza.
- *Molta autonomia* (creare e attivare routine e regole da sola): un errore su una casa vera costa troppo.
- *Tutto sul server di casa, senza modello esterno*: più semplice e più privato, ma limita la qualità dei compiti difficili. Si tiene come
  configurazione di partenza, e l'esterno resta un'opzione per chi la sceglie.
- *Compiti lunghi solo di notte*: più leggero per il server, ma «prenditi tempo» diventa «te lo dico domani».

## Conseguenze

- Una tabella dei **lavori** e una dei **modelli per scopo** (migrazioni), con proprietario e stato; i salvataggi non contengono i lavori.
- Un test per ogni regola di ciò che **non esce** verso un modello esterno e uno che, a esterno spento, prova che nessuna richiesta esce dalla rete locale.
- Un **banco dei piani**: dice dove il multi-agente aiuta e dove no, e dove non aiuta non si usa.
- `README.md` e `SECURITY.md` aggiornati con cosa esce, verso chi e quando, e con ciò che Shinra **non** può cambiare da sola.

## Ancora aperto

- Quali modelli esterni si supportano (uno, o un'interfaccia comune con più) — si decide con la misura del banco.
- Il costo: un tetto mensile in euro per scopo, e cosa succede quando si raggiunge.
- Se e quando passare da «propone» a «applica da sola le cose reversibili» (un ADR successivo, dopo mesi di uso).
