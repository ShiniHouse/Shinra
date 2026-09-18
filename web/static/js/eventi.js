// ============ EVENTI IN TEMPO REALE (/ws/eventi) ============
//
// PERCHE' UNA CADUTA VA CAPITA PRIMA DI ESSERE RITENTATA — issue #161
//
// Il browser non ci dice perche' l'handshake e' stato rifiutato: un 403 sul
// protocollo HTTP arriva a JavaScript come una chiusura 1006, la stessa che
// si prende quando il server e' spento. Codice alla mano, «non sei entrato» e
// «il server non c'e'» sono indistinguibili.
//
// Ritentare andava bene per il secondo caso e non per il primo. Con la
// sessione morta il ciclo ha ritentato per ore — 1, 2, 4, 8, 16, 30 secondi,
// poi ogni trenta — riempiendo il journal di 403 e non dicendo niente a chi
// guardava lo schermo. L'unico segnale era la spia che da verde diventava
// grigia. Nel frattempo la casa non avvisava piu': timer scaduti, promemoria,
// allarme intrusione, tutto zitto, con la dashboard che sembrava a posto.
//
// Allora glielo si chiede. `/api/auth/status` risponde 200 anche agli
// sconosciuti e dice `authenticated`, quindi separa i tre casi da sola:
// la chiamata fallisce -> il server non c'e', si ritenta; risponde «non sei
// autenticato» -> si smette e lo si dice; risponde «sei dentro» -> la caduta
// e' un'altra cosa, si ritenta.
let _eventiSocket = null;
let _eventiCollegati = false;
let _attesaRiconnessione = 1000;

function _segnalaStatoEventi(collegato) {
    _eventiCollegati = collegato;
    const spia = document.getElementById('stato-eventi');
    if (spia) {
        spia.className = `w-2 h-2 rounded-full ${collegato ? 'bg-emerald-500' : 'bg-slate-600'}`;
        spia.title = collegato
            ? 'Eventi del server collegati'
            : 'Eventi del server non collegati: gli avvisi arrivano solo da questa scheda';
    }
}

function collegaEventi() {
    if (_eventiSocket && _eventiSocket.readyState <= 1) return;
    const protocollo = location.protocol === 'https:' ? 'wss:' : 'ws:';
    try {
        _eventiSocket = new WebSocket(`${protocollo}//${location.host}/ws/eventi`);
    } catch (e) {
        console.warn('WebSocket eventi non disponibile:', e);
        return;
    }

    _eventiSocket.onopen = () => {
        _attesaRiconnessione = 1000;
        _segnalaStatoEventi(true);
    };

    _eventiSocket.onmessage = (msg) => {
        let evento;
        try {
            evento = JSON.parse(msg.data);
        } catch {
            return;
        }
        gestisciEvento(evento);
    };

    _eventiSocket.onclose = async () => {
        _segnalaStatoEventi(false);
        // Prima di ritentare, si chiede perche' e' caduta. Le due ragioni
        // vogliono due comportamenti opposti, e fin qui ne avevano uno solo.
        if (await _laSessioneEFinita()) {
            _sessioneScaduta();
            return;
        }
        // Riconnessione con attesa crescente, al massimo mezzo minuto:
        // un server riavviato non deve subire una raffica di tentativi.
        setTimeout(collegaEventi, _attesaRiconnessione);
        _attesaRiconnessione = Math.min(_attesaRiconnessione * 2, 30000);
    };

    _eventiSocket.onerror = () => {
        try {
            _eventiSocket.close();
        } catch {}
    };
}

// Ritentare a vuoto non e' innocuo: fa credere che manchi la rete, e
// nasconde l'unica cosa da fare, cioe' rientrare.
async function _laSessioneEFinita() {
    let risposta;
    try {
        risposta = await fetch('/api/auth/status', { headers: getAuthHeaders() });
    } catch {
        // Il server non risponde affatto: non e' un problema di sessione, e
        // ritentare e' esattamente la cosa giusta.
        return false;
    }
    if (!risposta.ok) return false;
    let stato;
    try {
        stato = await risposta.json();
    } catch {
        return false;
    }
    // `authenticated` basta da solo: a casa con l'autenticazione spenta
    // `/api/auth/status` risponde `true`, perche' li' non c'e' nessuna
    // sessione da perdere. E' una promessa di quella rotta, non un caso, e
    // `test_ad_autenticazione_spenta_lo_stato_dice_che_sei_dentro` la tiene
    // ferma: se cambiasse, questa riga comincerebbe a dire a tutta la casa
    // che la sessione e' scaduta.
    return !stato.authenticated;
}

// `/api/auth/status` e' fra le rotte che `sorvegliaIRifiuti` lascia passare
// apposta — risponde 200 agli sconosciuti, non 401 — quindi la barra non
// compare da sola e va chiesta qui.
function _sessioneScaduta() {
    _attesaRiconnessione = 1000;
    if (typeof mostraRifiuto === 'function') mostraRifiuto(401);
    const spia = document.getElementById('stato-eventi');
    if (spia) {
        spia.title = "La sessione e' scaduta: gli avvisi della casa non arrivano piu'. Rientra per riaverli.";
    }
}

function gestisciEvento(evento) {
    if (evento.tipo === 'timer.scaduto') {
        const t = _activeTimers.find((x) => x.id === evento.dati.id);
        if (t) {
            t.remaining_seconds = 0;
            t._notified = true;
        }
        playChimeAlert();
        speakText(evento.frase || 'Il timer è scaduto.');
        loadTimers();
    } else if (evento.tipo === 'promemoria.scaduto') {
        playChimeAlert();
        speakText(evento.frase || 'Hai un promemoria.');
        loadReminders();
    } else if (evento.tipo === 'ha.stato_cambiato') {
        aggiornaStatoCasa(evento.dati);
    } else if (evento.tipo.startsWith('persona.') || evento.tipo.startsWith('casa.')) {
        caricaPresenza();
    }
}

// ==================== CHI C'E' IN CASA ====================
// Riferimento: issue #22. La pastiglia mostra anche chi Home Assistant
// da' per uscito e a cui non stiamo ancora credendo: e' il ritardo
// contro i buchi del GPS, e vederlo spiega perche' la casa non ha
// ancora reagito.

async function caricaPresenza() {
    const pill = document.getElementById('presenza-pill');
    if (!pill) return;
    try {
        const res = await fetch('/api/presenza', { headers: getAuthHeaders() });
        if (!res.ok) return;
        const p = await res.json();

        if (!p.conosciuta) {
            // Nessuna persona configurata in Home Assistant: dire
            // «casa vuota» sarebbe una deduzione dal nulla.
            pill.style.display = 'none';
            return;
        }
        pill.style.display = 'flex';

        const punto = document.getElementById('presenza-punto');
        const testo = document.getElementById('presenza-testo');
        const quanti = (p.presenti || []).length;
        const attesa = (p.in_attesa || []).length;

        if (punto) punto.className = `w-2 h-2 rounded-full ${p.abitata ? 'bg-emerald-400' : 'bg-slate-500'}`;
        if (testo) {
            testo.textContent =
                quanti === 0 ? 'Casa vuota' : quanti === 1 ? '1 in casa' : `${quanti} in casa`;
        }
        pill.title = [
            (p.presenti || []).map((e) => e.split('.').pop()).join(', ') || 'nessuno in casa',
            attesa
                ? `in attesa di conferma: ${(p.in_attesa || []).map((e) => e.split('.').pop()).join(', ')}`
                : '',
        ]
            .filter(Boolean)
            .join(' — ');
    } catch (e) {
        console.warn('Presenza non disponibile:', e);
    }
}

// ==================== STATO DELLA CASA IN TEMPO REALE ====================
// Fino alla 0.2.0 lo stato dei dispositivi arrivava solo quando lo si
// chiedeva. Adesso Home Assistant lo manda quando cambia — anche
// quando a premere e' l'interruttore a muro, che e' il caso che una
// pagina che interroga a intervalli non vedrebbe mai in tempo.
// Riferimento: issue #19.

let _statiCasa = {};

function _chiaveStato(entityId) {
    // Gli identificativi contengono un punto: negli attributi `id` va
    // bene, ma romperebbe un selettore CSS. Qui non si usano
    // selettori, e getElementById non ha il problema — la chiave resta
    // comunque pulita, cosi' non diventa un problema domani.
    return (entityId || '').replace(/[^a-zA-Z0-9_-]/g, '_');
}

function _testoStato(entityId) {
    const s = _statiCasa[entityId];
    return s ? s.stato : '';
}

function aggiornaStatoCasa(dati) {
    if (!dati || !dati.entity_id) return;
    _statiCasa[dati.entity_id] = dati;

    const el = document.getElementById(`stato-${_chiaveStato(dati.entity_id)}`);
    if (!el) return;

    el.textContent = dati.stato || '';
    const acceso = ['on', 'open', 'playing', 'home', 'unlocked'].includes((dati.stato || '').toLowerCase());
    el.className = `text-[10px] font-semibold ${acceso ? 'text-emerald-400' : 'text-slate-500'}`;

    // Un lampo breve: senza, un cambiamento che arriva mentre si
    // guarda altrove passa inosservato e sembra che non sia successo
    // niente.
    el.animate([{ opacity: 0.35 }, { opacity: 1 }], { duration: 400, easing: 'ease-out' });
}
