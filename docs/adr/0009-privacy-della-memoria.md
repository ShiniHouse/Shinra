# 0009 — Chi vede e chi può cambiare ciò che Shinra ricorda

- **Stato:** Proposto
- **Data:** 2026-10-13
- **Attuazione:** milestone `v0.8.0`, issue #243 (schema: #245, API: #249, cancellazione: #253)

> **Stato: proposto, con due scelte già prese dal proprietario (2026-10-14).** L'amministratore **non** vede i ricordi privati
> degli altri profili, e un adulto **non** vede cosa è ricordato di un minore: *ognuno vede solo i propri*. Il resto è ancora
> una proposta da leggere; lo stato passa a `Accettato` quando il proprietario lo dice.

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
   **non dai backup vecchi**: lo si dice in chiaro, con la durata di conservazione dei backup. Un ripristino non deve riportare un
   ricordo cancellato: si tiene l'elenco degli id cancellati finché esistono backup che li contengono.
7. **Il grafo del Cervello** non mostra mai il testo di un ricordo.

## Alternative scartate

- *Tutto della casa, con filtro nel prompt*: un errore di filtro espone tutto; la separazione deve stare nei dati.
- *Cifrare i ricordi per profilo*: il database è già non cifrato a riposo (dichiarato nell'ADR 0010); cifrare solo questi dà una falsa
  sicurezza senza gestione delle chiavi.

## Conseguenze

- Lo schema (#245) deve portare `proprietario` e `stato` dal primo giorno.
- L'API e la vista (#249, #250) filtrano per profilo **sul server**, non nell'interfaccia.
- Serve un test per ogni coppia ruolo/ambito, e uno che cerchi un ricordo privato nel prompt di un altro profilo.

## Da decidere prima dell'accettazione

- ~~L'amministratore vede il privato degli altri?~~ **Deciso: no** (2026-10-14).
- ~~Cosa vede un adulto dei ricordi di un minore?~~ **Deciso: niente**, ognuno vede i propri (2026-10-14).
- Per quanto si tengono i backup che contengono un ricordo cancellato.
- Conseguenza da guardare insieme: se nessuno può leggere il privato di un altro, «dimentica tutto di me» è l'unico modo per
  un amministratore di aiutare chi ha perso l'accesso? (no: lo fa solo il proprietario del ricordo; chi perde l'accesso
  riparte da un profilo nuovo).
