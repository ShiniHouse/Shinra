---
title: "feat(canali): satelliti vocali per stanza"
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: integrazioni"]
---

## Contesto

L'unico punto di ascolto vocale distribuito e' Amazon Echo, cioe' un servizio
cloud di terze parti. Con parola di attivazione (issue #30) e riconoscimento
locale (issue #31) disponibili, un dispositivo da poche decine di euro per
stanza diventa l'alternativa aperta.

## Cosa fare

- [ ] Protocollo satellite: registrazione, invio audio, ricezione risposta, indicazione di stato
- [ ] Immagine di riferimento per Raspberry Pi con microfono e altoparlante
- [ ] Valutare la compatibilita' con Wyoming, gia' usato dall'ecosistema Home Assistant, invece di un protocollo proprietario
- [ ] Consapevolezza della stanza: un satellite dichiara dove si trova, cosi' «accendi la luce» accende quella giusta
- [ ] Gestione di piu' satelliti che sentono la stessa frase: risponde solo il piu' vicino

## Criteri di accettazione

- [ ] Un satellite in cucina risponde e comanda i dispositivi della cucina
- [ ] «Accendi la luce» senza specificare la stanza agisce sulla stanza del satellite
- [ ] Due satelliti che sentono la stessa frase non rispondono entrambi
