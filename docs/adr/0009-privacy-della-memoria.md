# 0009 — Chi vede e chi può cambiare ciò che Shinra ricorda

- **Stato:** Accettato
- **Data:** 2026-10-13
- **Attuazione:** milestone `v0.8.0`, issue #243 (schema: #245, API: #249, cancellazione: #253)

> **Accettato il 2026-10-20** dal proprietario, dopo averlo visto funzionare: tutto ciò che sta sotto è in `main` e provato sul
> server di casa (schema, API, vista, riassunti, sogno, cancellazione). Due scelte erano già state prese il 2026-10-14:
> l'amministratore **non** vede i ricordi privati degli altri profili, e un adulto **non** vede cosa è ricordato di un minore:
> *ognuno vede solo i propri*. Il punto 6 (backup) è accettato **com'è oggi**, con i due limiti scritti lì sotto.

## Contesto

Oggi la tabella `knowledge` è **della casa**: un fatto non ha un proprietario e chi ha il permesso `conoscenza.leggi` li legge
tutti. Va bene per «il wifi è sul router». Non regge «cosa sa Shinra di *me*»: la memoria personale di un adulto non deve finire
nel prompt di un bambino né nella lista di un ospite, e un profilo deve poter chiedere «dimentica tutto di me». Si aggiunge il
**luogo** come terzo ambito (proposta dei luoghi, #345).

## Proposta

1. **Due ambiti, più il luogo.** *Casa* (condivisa, default per ciò che arriva dall'intervista sulla casa) e *profilo* (privata, default
   per ciò che una persona dice di sé in conversazione). Un ricordo può avere anche un luogo.
2. **Chi legge e chi scrive.** Il profilo legge e scrive i propri ricordi privati, **e solo quelli**. La casa la legge chi ha
   `conoscenza.leggi`, la scrive chi ha `conoscenza.scrivi`. **L'amministratore non vede il privato di un altro profilo**
   (scelta del proprietario, 2026-10-14): non c'è un'eccezione «per emergenza».
3. **Minori** (`teen`, `child`, `restricted_topics`): ricordano ciò che serve alla casa; i temi limitati non diventano ricordi;
   **un adulto non vede cosa è ricordato di un minore** (scelta del proprietario, 2026-10-14): il minore vede i propri, come
   tutti. Quello che interessa alla casa (orari, allergie, regole) è un ricordo **della casa**, e quello lo vedono tutti.
4. **Ospiti: nessuna memoria persistente.**
5. **Cosa non si ricorda mai:** PIN, token, codici dell'allarme, numeri di carte. Si riusa `registro.oscura` come filtro in scrittura.
6. **Backup e «dimentica».** Il backup contiene i ricordi (schema nuovo con migrazione). Un «dimentica» cancella dal database e
   **non dai backup vecchi**: lo si dice in chiaro (`docs/MEMORIA.md`). **Com'è oggi, accettato:**
   - il salvataggio contiene **anche i ricordi privati di tutti**: chi apre il file sul server li legge, anche se
     dall'interfaccia non può. Il proprietario ha scelto di lasciarli (2026-10-20: «non togliere nulla»), perché toglierli
     vorrebbe dire perderli in un ripristino;
   - i backup di `deploy.sh` si tengono gli ultimi 10; un salvataggio con un ricordo cancellato lo contiene finché non esce
     da quelli;
   - **l'elenco degli id cancellati** (tabella `ricordi_cancellati`, solo identificativo e momento, mai il testo) impedisce a un
     ripristino di riportare un ricordo cancellato dopo quel salvataggio; l'anteprima dice quanti ne salta. Chiude il limite
     noto, ma **solo per le cancellazioni fatte da questa versione in poi**: un ricordo cancellato prima non è nell'elenco.
7. **Il grafo del Cervello** non mostra mai il testo di un ricordo.

## Alternative scartate

- *Tutto della casa, con filtro nel prompt*: un errore di filtro espone tutto; la separazione deve stare nei dati.
- *Cifrare i ricordi per profilo*: il database è già non cifrato a riposo (dichiarato nell'ADR 0010); cifrare solo questi dà una falsa
  sicurezza senza gestione delle chiavi.

## Conseguenze

- Lo schema (#245) deve portare `proprietario` e `stato` dal primo giorno.
- L'API e la vista (#249, #250) filtrano per profilo **sul server**, non nell'interfaccia.
- Serve un test per ogni coppia ruolo/ambito, e uno che cerchi un ricordo privato nel prompt di un altro profilo.

## Decisioni prese

- ~~L'amministratore vede il privato degli altri?~~ **Deciso: no** (2026-10-14).
- ~~Cosa vede un adulto dei ricordi di un minore?~~ **Deciso: niente**, ognuno vede i propri (2026-10-14).
- ~~Per quanto si tengono i backup che contengono un ricordo cancellato?~~ **Gli ultimi 10 di `deploy.sh`**; i ricordi privati
  restano nel salvataggio (2026-10-20).
- «Dimentica tutto di me» lo fa solo il proprietario del ricordo; chi perde l'accesso riparte da un profilo nuovo.

## Ancora aperto

- Nulla di noto. (L'elenco degli id cancellati da non rimettere in un ripristino è fatto: punto 6.)
