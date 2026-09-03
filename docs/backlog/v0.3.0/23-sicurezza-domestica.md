---
title: "feat(sicurezza-casa): allarme, aperture e notifiche di intrusione"
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Nessuna gestione dell'allarme, delle serrature come sistema, delle telecamere o
dei sensori di apertura. E' il dominio piu' importante fra quelli scoperti,
perche' e' quello per cui una famiglia installa la domotica.

## Cosa fare

- [ ] Tool per `alarm_control_panel`: arma in casa, arma fuori casa, disarma
- [ ] Stato aggregato delle aperture: quali porte e finestre risultano aperte
- [ ] Controllo di coerenza all'armamento: rifiuta se una finestra e' aperta e lo dice
- [ ] Notifica all'intrusione, sui canali della issue #29
- [ ] Simulazione di presenza in vacanza, con accensioni verosimili e non a orario fisso
- [ ] Il disarmo richiede autenticazione forte e non e' mai possibile da un canale non autenticato

## Criteri di accettazione

- [ ] «Arma l'allarme» con una finestra aperta avvisa invece di armare in silenzio
- [ ] «Sono chiuse tutte le finestre?» risponde con l'elenco reale
- [ ] Il disarmo da Alexa richiede una conferma aggiuntiva
- [ ] La simulazione di presenza non ripete lo stesso schema due sere di fila
