# Primi passi — dal primo accesso alla prima automazione

Shinra è installata e sei entrato con il PIN. Questa guida copre la mezz'ora
dopo: da una dashboard che non sa niente della tua casa a una casa che fa
qualcosa da sola.

Se l'installazione non è ancora fatta, sta nel
[README](../README.md#-installazione--configurazione-su-serverlinuxdebian).
Se qualcosa non funziona, c'è [PROBLEMI.md](PROBLEMI.md).

I passi sono in ordine e ognuno dipende dal precedente. Il quinto è
facoltativo.

---

## 1. Cambia il PIN, e dai un nome a chi vive in casa

Il profilo *Amministratore* è nato con un PIN generato a caso, stampato nel
log una volta sola. Il primo gesto è cambiarlo.

**Impostazioni → Persone e accessi**, oppure la scheda **Persone**.

Poi aggiungi chi vive in casa. Non è una formalità: Shinra risponde per
persona — il timer che metti tu è tuo, i promemoria sono di chi li ha
chiesti, e il registro di cosa è successo in casa dice *chi*. Un solo
profilo condiviso funziona, ma butta via metà di quello che il sistema sa
fare.

Ogni profilo ha un **ruolo**, e il ruolo decide cosa può fare. Le impostazioni
del server, i profili altrui e il registro delle azioni sono roba da
amministratore: un ragazzo con un profilo suo può parlare con la casa e
accendere le luci senza poter cambiare come funziona.

---

## 2. Collega Home Assistant

Senza questo passo Shinra parla ma non tocca niente.

Serve un **token di lunga durata** di Home Assistant: si crea dal profilo
utente di HA, in fondo alla pagina, sotto *Token di accesso a lunga durata*.

Il token **non va in `config.yaml`**. Va in `.env`, che non è versionato e non
finisce in nessun backup di configurazione:

```bash
echo 'SHINRA_HA_TOKEN=incolla-qui-il-token' >> /opt/Shinra/.env
chmod 600 /opt/Shinra/.env
sudo systemctl restart shinra
```

L'indirizzo di Home Assistant si imposta invece dalla dashboard, in
**Impostazioni → Home Assistant**, e lì c'è anche un pulsante che prova la
connessione e ti dice cosa ha risposto.

> Un token incollato in una chat, in un'issue o in uno screenshot è un token
> da revocare, non da nascondere: chi lo ha visto può spegnere le luci di casa
> tua. Si revoca dalla stessa pagina di Home Assistant dove lo hai creato.

---

## 3. Dai i nomi alle tue cose

Questo è il passo che cambia davvero le risposte, ed è l'unico che **solo tu**
puoi fare: Home Assistant sa che esiste `light.yeelight_desk`, ma che quella
sia *«la luce della scrivania»* lo sai tu.

Vai su **Mappa dispositivi** e premi **Scopri dispositivi HA**: compare tutto
quello che Home Assistant espone. Per ognuno che ti interessa scrivi il nome
con cui lo chiami davvero, e salvi.

Consigli che vengono dall'uso:

- **Nomina poco e bene.** Dieci alias giusti valgono più di ottanta presi da
  una lista: il nome che non useresti mai a voce è rumore.
- **Usa il nome della stanza come lo dici tu.** Se in casa dite «di sopra» e
  non «primo piano», scrivi «di sopra».
- **Un dispositivo può avere più nomi.** «Lampada del comodino» e «abat-jour»
  sono la stessa cosa per te: dillo a Shinra.

Da qui in poi «accendi la luce della scrivania» funziona.

---

## 4. La prima automazione, in un minuto

**Automazioni e routine → «Alle 23, spegni tutto»**.

È una scorciatoia: un innesco, un'azione, niente disegno. Scegli *quando* —
a un orario, all'alba, al tramonto, quando un valore supera una soglia,
quando succede qualcosa in casa — scegli *cosa*, e salvi.

La scheda ti dice tre cose per ogni automazione: **quando scatta**, **quando
scatterà la prossima volta**, e **com'è andata l'ultima**. La seconda è quella
che serve: un'automazione che dice «prossima: mai» è un'automazione scritta
male, e lo vedi subito invece che fra tre giorni.

Puoi anche **provarla** senza aspettare l'ora: il pulsante di prova la fa
girare e ti dice quale ramo ha preso e perché.

### Quando la scorciatoia non basta

Rami, condizioni, ritardi e sequenze non stanno in una riga: per quelli c'è
l'**editor a blocchi**, nella stessa scheda. Si trascinano i blocchi, si
tirano i cavi da un pin all'altro, e si salva.

La scorciatoia e l'editor lavorano sulle stesse automazioni: una fatta di qua
si apre di là.

---

## 5. Facoltativo — l'intervista di apprendimento

**Conoscenza casa → Shinra Istruisci**.

Sono sei domande sulla casa, sulle abitudini, su chi ci vive. Quello che
racconti finisce nella conoscenza e viene ripescato quando serve a rispondere.

Due cose da sapere prima di cominciare, perché ti risparmiano tempo:

- **Serve un modello capace.** L'intervista chiede al modello di interpretare
  una frase e tirarne fuori i fatti. Con un modello da un miliardo di
  parametri non ci riesce, e te lo dice: «non sono riuscita a ricavarne niente
  di preciso». Se lo dice a ogni domanda, il problema è il modello — vedi
  [PROBLEMI.md](PROBLEMI.md#la-chat-risponde-male-o-non-fa-niente).
- **Prima di salvare ti fa vedere cosa ha capito.** Leggilo. Se ha capito
  male, riscrivi la frase come la diresti tu e lei rifà; se non ti va,
  rispondi «no» e passa oltre. Quello che salvi resta, e una frase sbagliata
  lì dentro torna a galla mesi dopo in una risposta strana.

I fatti servono a far **dire** cose. Per far **fare** servono gli alias del
passo 3 e le automazioni del passo 4.

---

## Dove guardare quando qualcosa non torna

| Domanda | Dove si risponde |
| :--- | :--- |
| Shinra ha capito il comando? | Console, la colonna di destra |
| L'automazione è scattata? | Automazioni e routine, riga per riga |
| Chi ha fatto cosa, e com'è andata | Registro delle azioni (solo amministratori) |
| Il servizio sta bene? | `journalctl -u shinra -f` |

E se niente di tutto questo basta: [PROBLEMI.md](PROBLEMI.md).
