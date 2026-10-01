// Il punto d'ingresso dei moduli (#34, ADR 0006).
//
// Importa ogni area per i suoi effetti: registrare i gesti, mettersi in
// ascolto, avviare la pagina. Le dipendenze fra un'area e l'altra stanno
// negli `import` di ciascun file, non piu' nell'ordine di questo elenco;
// l'elenco resta quello di prima solo perche' e' quello provato.

import './stato.js';
import './gesti.js';
import './sicurezza.js';
import './avvio.js';
import './accesso.js';
import './navigazione.js';
import './voce.js';
import './conversazione.js';
import './conoscenza.js';
import './istruisci.js';
import './fonti.js';
import './dispositivi.js';
import './timer.js';
import './eventi.js';
import './routine.js';
import './tela.js';
import './tela_disegno.js';
import './tela_nodi.js';
import './regole.js';
import './utenti.js';
import './ruoli.js';
import './passkey.js';
import './impostazioni.js';
import './cervello_fisica.js';
import './cervello_stile.js';
import './cervello_attivita.js';
import './cervello_disegno.js';
import './cervello.js';
