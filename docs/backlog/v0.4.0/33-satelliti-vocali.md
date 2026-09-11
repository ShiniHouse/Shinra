---
title: "feat(canali): satelliti vocali per stanza"
issue: 33
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: integrazioni"]
---

## Contesto

L'unico punto di ascolto vocale distribuito e' Amazon Echo, cioe' un servizio
cloud di terze parti. Con parola di attivazione (issue #30) e riconoscimento
locale (issue #31) disponibili, un dispositivo da poche decine di euro per
stanza diventa l'alternativa aperta.

### Cosa e' cambiato rispetto al piano

*Aggiunto l'11 settembre 2026, lavorando alla scheda.*

La scheda presupponeva hardware — un Raspberry per stanza — che non c'e'.
Lavorandoci e' venuto fuori che **il pezzo che conta non e' il microfono**:
il telefono e il portatile un microfono ce l'hanno gia'. Quello che manca e'
che la casa sappia **da dove** arriva la frase.

Quindi la dashboard aperta in cucina e' diventata un satellite. Non e' un
ripiego in attesa del Raspberry: e' la stessa cosa con un involucro diverso,
e il giorno in cui arrivera' un dispositivo dedicato parlera' lo stesso
protocollo.

## Cosa e' stato fatto

- [x] **Consapevolezza della stanza**: un punto di ascolto dichiara dove si
      trova, e «accendi la luce» accende quella di li'.
- [x] **Piu' satelliti che sentono la stessa frase**: risponde chi arriva per
      primo, gli altri ricevono «gia' presa in carico» e non eseguono niente.
- [x] Protocollo minimo: registrazione, elenco di chi ascolta, e uscita
      automatica dall'elenco dopo cinque minuti di silenzio.
- [x] La dashboard si dichiara punto di ascolto, con la stanza scelta sotto
      il microfono — dove si parla, non in un pannello di impostazioni.

### Il difetto trovato strada facendo

**«Accendi la luce» ne accendeva una a caso.** `resolve_alias_or_entity`
cercava l'alias con un `riferimento in nome`: «luce» corrispondeva a «luce
cucina», «luce salotto» e «luce bagno» insieme, e vinceva quella che
l'archivio restituiva per prima. Nessun avviso, nessun modo di accorgersene
se non guardando quale lampadina si accende.

Non era un difetto dei satelliti — c'era da prima e riguardava chiunque — ma
e' saltato fuori qui perche' e' esattamente la domanda che una stanza serve a
sciogliere. Adesso un riferimento ambiguo **si dichiara ambiguo**: o la
stanza sceglie, o la casa chiede «quale?» elencando le alternative.

Il vocabolario delle stanze sta in `domain/stanze.py`, e la stanza di chi
parla viaggia nel contesto della richiesta come gia' fanno l'attore e il
canale: i tool che comandano la casa sono una dozzina e nessuno di loro ha
ragione di sapere che esistono i satelliti.

## Criteri di accettazione

- [x] Un satellite in cucina risponde e comanda i dispositivi della cucina
- [x] «Accendi la luce» senza specificare la stanza agisce sulla stanza del
      satellite
- [x] Due satelliti che sentono la stessa frase non rispondono entrambi

## Cosa resta, e va in v0.5.0

- [ ] **Immagine di riferimento per Raspberry Pi** con microfono e
      altoparlante. Serve l'hardware per scriverla e per provarla: un'immagine
      mai avviata e' un file che sembra una soluzione.
- [ ] **Compatibilita' con Wyoming**, il protocollo gia' usato
      dall'ecosistema Home Assistant. Vale la pena farlo *invece* di un
      protocollo proprietario, ma conviene farlo quando c'e' un satellite
      vero con cui provarlo: oggi si scriverebbe contro una specifica, non
      contro un dispositivo.

Il registro dei satelliti sta **in memoria**, e per adesso e' giusto cosi':
un elenco salvato su disco sopravviverebbe ai dispositivi spenti, cioe'
manderebbe risposte in stanze vuote. Quando i satelliti saranno dispositivi
fissi, la scelta andra' rivista.

## Da verificare in casa

- [ ] Apri la dashboard sul telefono, scrivi «Cucina» sotto il microfono, e
      chiedi «accendi la luce»: deve accendersi quella della cucina. Servono
      alias con la stanza compilata nella Mappa Dispositivi.
- [ ] Ripeti dal portatile dichiarando «Salotto»: la stessa frase deve
      accendere un'altra luce.
- [ ] Senza dichiarare nessuna stanza, «accendi la luce» deve **chiedere
      quale** invece di accenderne una.
- [ ] Con due dispositivi aperti nella stessa stanza, mandare la stessa frase
      da entrambi entro un paio di secondi: deve eseguirsi una volta sola.
