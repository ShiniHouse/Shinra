# Le conferme — le azioni che Shinra non fa sulla parola del modello

Per accendere una luce basta una frase. Per aprire una porta di casa no:
il modello che sceglie lo strumento può aver capito male, o qualcuno può
avergli fatto dire apposta una cosa che non va detta. Per questo Shinra
distingue le azioni **sicure**, che partono e basta, da quelle **sensibili**,
che non partono finché *una persona* non ha detto di sì. Questa guida dice
quali sono, come si risponde e cosa succede se non si risponde.

Il perché sta in [ADR 0004](adr/0004-identita-ruoli-e-permessi.md) e nella
scheda #192; qui c'è come funziona per chi la usa. Se qualcosa non funziona,
c'è [PROBLEMI.md](PROBLEMI.md).

---

## 1. Quali azioni chiedono conferma

| Cosa | Chiede conferma | Non la chiede |
| :--- | :--- | :--- |
| **Serrature** | aprire, sbloccare, qualunque altra azione | chiudere a chiave, chiedere lo stato |
| **Allarme** | disinserire, qualunque altra azione | inserirlo (casa, fuori), chiedere lo stato |
| **Garage, portoni, cancelli, basculanti e porte** (le coperture di Home Assistant che hanno uno di questi nomi) | aprirli | chiuderli, fermarli, chiedere lo stato |
| **Script** di Home Assistant | sempre: non c'è modo di sapere cosa fanno dentro | — |
| Luci, clima, tapparelle normali, prese, TV, aspirapolvere, energia, meteo, liste, promemoria… | — | partono |

Due cose da sapere:

- **Nel dubbio si chiede.** Un'azione senza il verbo chiaro (per esempio una
  serratura senza dire se aprire o chiudere) è trattata come sensibile. E uno
  strumento nuovo che nessuno ha classificato è sensibile per difetto: costa
  una domanda in più, non una porta aperta.
- **Una rete di sicurezza in fondo.** Se una routine o una modalità, scritta da
  una persona, contiene un passo «sblocca la porta» e a lanciarla è il modello,
  quel passo si ferma prima di arrivare a Home Assistant. Lì non c'è modo di
  chiedere conferma — è una chiamata, non una conversazione — quindi non parte.

---

## 2. Come si risponde

Dici, o scrivi: «apri la serratura dell'ingresso». Shinra non la apre e
risponde:

> Sto per eseguire: *comanda serratura lock.ingresso*. Confermi? Rispondi «sì»
> o «no» entro 3 minuti.

(La descrizione dell'azione è il nome dello strumento e il dispositivo: è
tecnica, ma dice esattamente cosa sta per partire.)

Rispondi **sullo stesso canale** — la stessa chat della dashboard, o lo stesso
dispositivo a voce — e **tu**, non un'altra persona:

| Per confermare | Per annullare |
| :--- | :--- |
| «sì», «si», «sì grazie», «confermo», «ok», «va bene», «certo», «procedi», «fallo» | «no», «no grazie», «annulla», «lascia stare», «non farlo», «fermati», «rifiuto», «stop» |

Il «sì» non lo scrive il modello: lo legge un intento che viene prima del
modello e confronta chi parla con chi aveva chiesto.

---

## 3. Le regole, e il loro perché

| Regola | Perché |
| :--- | :--- |
| **La conferma è di una persona.** La conferma di Sam non apre la porta chiesta da Alessio | Chi conferma deve essere chi ha chiesto |
| **È di un'azione sola**, quella esatta, con i suoi argomenti | Il «sì» esegue quella, non qualcosa che il modello ha rimesso insieme nel frattempo |
| **Si usa una volta.** Una richiesta nuova sostituisce la precedente | Un vecchio «sì» non deve restare in giro |
| **Scade dopo 3 minuti.** Alla scadenza non parte niente | Il tempo di rispondere, non quello perché un «sì» detto per altro apra la porta |
| **Non sa chi sei, non parte.** Una voce che nessun profilo riconosce, o un comando senza un canale a cui chiedere, non possono ricevere una conferma | Senza sapere chi risponde non si può dire che sia la persona giusta |

Se rispondi dopo i tre minuti, o senza aver chiesto niente: «Non c'è niente da
confermare». Se la conferma scade: «La conferma è scaduta: non ho fatto niente.
Se vuoi, richiedilo». Se non c'è nessuno a cui chiedere: «Non lo faccio: non
c'è nessuno a cui chiedere conferma. Va richiesta da una persona, dalla
dashboard o a voce».

---

## 4. Cosa resta scritto

Ogni richiesta, conferma, rifiuto, scadenza e annullamento va nel **registro
delle azioni**, con il nome dello strumento e il bersaglio. **Mai gli argomenti**:
potrebbero contenere il codice dell'allarme.

---

## 5. Provarla in due minuti

1. Dalla chat della dashboard scrivi: «apri la serratura dell'ingresso» (o il
   nome che hai dato alla tua serratura).
2. Shinra risponde con la domanda e **non apre niente**: controlla che la
   serratura non si sia mossa.
3. Scrivi «no»: «Va bene, non faccio niente.»
4. Ripeti, e questa volta scrivi «sì» entro tre minuti: allora sì, la apre.

Se al punto 2 la serratura si apre senza domande, **non è andato come doveva**:
apri una issue con la frase che hai usato e con l'ora, e controlla nel registro
cosa è stato registrato.
