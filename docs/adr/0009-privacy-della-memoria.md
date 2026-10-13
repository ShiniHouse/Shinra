# 0009 — Chi vede e chi può cambiare ciò che Shinra ricorda

- **Stato:** Proposto
- **Data:** 2026-10-13
- **Attuazione:** milestone `v0.8.0`, issue #243 (schema: #245, API: #249, cancellazione: #253)

> Bozza scritta per essere discussa: **nessuna di queste scelte è decisa** finché il proprietario non porta lo stato a `Accettato`.

## Contesto

Oggi la tabella `knowledge` è **della casa**: un fatto non ha un proprietario e chi ha il permesso `conoscenza.leggi` li legge
tutti. Va bene per «il wifi è sul router». Non regge «cosa sa Shinra di *me*»: la memoria personale di un adulto non deve finire
nel prompt di un bambino né nella lista di un ospite, e un profilo deve poter chiedere «dimentica tutto di me». Si aggiunge il
**luogo** come terzo ambito (proposta dei luoghi, #345).

## Proposta

1. **Due ambiti, più il luogo.** *Casa* (condivisa, default per ciò che arriva dall'intervista sulla casa) e *profilo* (privata, default
   per ciò che una persona dice di sé in conversazione). Un ricordo può avere anche un luogo.
2. **Chi legge e chi scrive.** Il profilo legge e scrive i propri ricordi privati. La casa la legge chi ha `conoscenza.leggi`, la
   scrive chi ha `conoscenza.scrivi`. **L'amministratore non vede il privato di un altro profilo**, salvo una scelta esplicita
   e registrata del proprietario.
3. **Minori** (`teen`, `child`, `restricted_topics`): ricordano ciò che serve alla casa; i temi limitati non diventano ricordi;
   un adulto con il permesso può vedere cosa è ricordato di un minore (decisione da confermare).
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

- L'amministratore deve poter vedere il privato in caso di emergenza? (proposta: no)
- Cosa vede un adulto dei ricordi di un minore.
- Per quanto si tengono i backup che contengono un ricordo cancellato.
