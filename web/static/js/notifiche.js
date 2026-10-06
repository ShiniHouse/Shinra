// Le notifiche push, dal dispositivo (issue #29, completata).
//
// Il server sapeva gia' mandarle: le chiavi, l'API, il service worker che le riceve. Mancava chi chiede il
// permesso al browser e iscrive il dispositivo, cioe' l'unico passo che un'interfaccia deve fare — e senza cui
// «un avviso al telefono di chi deve saperlo» restava una frase del README. Il Cervello lo diceva: «Notifiche
// push: fermo, nessun dispositivo iscritto».
//
// Il giro, in ordine: il browser le sa fare? il server le ha? l'utente le ha bloccate? E solo allora il pulsante,
// che chiede il permesso **dentro il clic** (altrimenti il browser lo ignora), si iscrive presso il proprio
// servizio push e consegna al server l'indirizzo e le chiavi. L'iscrizione e' di questo dispositivo: per toglierne
// un altro bisogna farlo da quello.
//
// Su iPhone e iPad le notifiche esistono solo per l'app **aggiunta alla schermata Home** (iOS 16.4 o piu'): da
// Safari «normale» `PushManager` non c'e', e la scheda lo dice con le istruzioni invece di mostrare un pulsante muto.

import { Gesti } from './gesti.js';
import { _args, _html } from './sicurezza.js';
import { getAuthHeaders } from './accesso.js';
import { safeCreateIcons } from './avvio.js';

const CATEGORIE = {
    sicurezza: 'Sicurezza (allarme, porte)',
    promemoria: 'Promemoria',
    timer: 'Timer',
    presenza: 'Presenza',
    energia: 'Energia',
    manutenzione: 'Manutenzione e scadenze',
};
const CANALI = { web: 'Nella dashboard', push: 'Sul telefono', voce: 'A voce' };

const $ = (id) => document.getElementById(id);

// ------------------------------------------------------------------ server

async function _chiama(percorso, metodo = 'GET', corpo = null) {
    const risposta = await fetch(percorso, {
        method: metodo,
        headers: { ...getAuthHeaders(), ...(corpo ? { 'Content-Type': 'application/json' } : {}) },
        body: corpo ? JSON.stringify(corpo) : undefined,
    });
    if (!risposta.ok) {
        let motivo = `Il server ha risposto ${risposta.status}.`;
        try {
            motivo = (await risposta.json()).detail || motivo;
        } catch {
            /* il corpo non e' JSON: vale il codice */
        }
        throw new Error(motivo);
    }
    return risposta.json();
}

function _chiaveInByte(base64url) {
    const riempimento = '='.repeat((4 - (base64url.length % 4)) % 4);
    const grezzo = atob((base64url + riempimento).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(grezzo, (c) => c.charCodeAt(0));
}

/** «iPhone · Safari», «Windows · Edge»: per riconoscere il proprio telefono in un elenco. */
function _nomeDelDispositivo() {
    const ua = navigator.userAgent || '';
    const sistema = /iPhone/.test(ua)
        ? 'iPhone'
        : /iPad/.test(ua)
          ? 'iPad'
          : /Android/.test(ua)
            ? 'Android'
            : /Windows/.test(ua)
              ? 'Windows'
              : /Mac/.test(ua)
                ? 'Mac'
                : /Linux/.test(ua)
                  ? 'Linux'
                  : 'Dispositivo';
    const programma = /Edg\//.test(ua)
        ? 'Edge'
        : /Firefox\//.test(ua)
          ? 'Firefox'
          : /Chrome\//.test(ua)
            ? 'Chrome'
            : /Safari\//.test(ua)
              ? 'Safari'
              : 'browser';
    return `${sistema} · ${programma}`;
}

// ------------------------------------------------------------------ stato

const _eIos = () => /iPhone|iPad|iPod/.test(navigator.userAgent || '');

// La registrazione del service worker, **senza passare da `serviceWorker.ready`**.
//
// `ready` si risolve solo se il worker controlla *questa pagina*: bastava uno scope diverso da quello della pagina
// (era il caso: il worker sta in /static/, la pagina in /) perche' non si risolvesse mai, e sul telefono la sezione
// restava muta. Ma per iscriversi alle notifiche il controllo della pagina non serve: basta la registrazione, e
// `register()` la restituisce, anche se esiste gia'. Si prova prima con lo scope della radice (il server lo consente),
// poi con quello predefinito; e se il worker non si attiva si dice perche', con le parole del browser.
async function _registrazione() {
    let registrazione;
    try {
        registrazione = await navigator.serviceWorker.register('/static/sw.js', { scope: '/' });
    } catch {
        registrazione = await navigator.serviceWorker.register('/static/sw.js');
    }
    if (registrazione.active) return registrazione;
    const lavoratore = registrazione.installing || registrazione.waiting;
    if (!lavoratore) throw new Error('il service worker non parte');
    await new Promise((ok, rifiuta) => {
        const scaduto = setTimeout(() => rifiuta(new Error('il service worker non si attiva')), 8000);
        lavoratore.addEventListener('statechange', () => {
            if (lavoratore.state === 'activated') {
                clearTimeout(scaduto);
                ok();
            } else if (lavoratore.state === 'redundant') {
                clearTimeout(scaduto);
                rifiuta(new Error('il service worker non si è installato'));
            }
        });
    });
    return registrazione;
}

/** Cosa si puo' dire di questo dispositivo: `{ tipo, ... }`. Non fa niente, guarda soltanto. */
async function _stato() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
        return { tipo: _eIos() ? 'ios_senza_app' : 'non_supportato' };
    }
    let chiave;
    try {
        chiave = await _chiama('/api/notifiche/chiave');
    } catch (errore) {
        return { tipo: 'errore', motivo: errore.message };
    }
    if (!chiave.disponibile) return { tipo: 'server_senza_notifiche' };
    if (Notification.permission === 'denied') return { tipo: 'bloccate' };

    const iscrizione = await (await _registrazione()).pushManager.getSubscription();
    return iscrizione && Notification.permission === 'granted'
        ? { tipo: 'attive', iscrizione }
        : { tipo: 'da_attivare', chiave: chiave.chiave };
}

// ------------------------------------------------------------------ disegno

const MESSAGGI = {
    ios_senza_app:
        "Su iPhone e iPad le notifiche funzionano solo dall'app: tocca Condividi, scegli «Aggiungi a schermata Home», apri Shinra da lì e torna qui.",
    non_supportato: 'Questo browser non sa ricevere notifiche push. Prova con Chrome, Edge o Firefox.',
    server_senza_notifiche:
        'Il server non ha le notifiche: manca la libreria `pywebpush` o le chiavi non si sono potute generare. Vedi i log di Shinra.',
    bloccate:
        "Hai bloccato le notifiche per questo sito. Sbloccale dalle impostazioni del browser (l'icona del lucchetto vicino all'indirizzo) e torna qui.",
};

function _dispositivi(elenco) {
    if (!elenco.length) return _html`<p class="text-slate-500">Nessun dispositivo iscritto.</p>`;
    return _html`<ul class="divide-y divide-slate-800">${elenco.map(
        (d) =>
            _html`<li class="py-1.5 flex justify-between gap-2"><span class="text-slate-200">${d.nome || 'Dispositivo'}</span><span class="text-slate-500">${d.ultimo_invio ? `ultimo avviso ${String(d.ultimo_invio).slice(0, 10)}` : 'nessun avviso ancora'}</span></li>`,
    )}</ul>`;
}

function _preferenze(p) {
    const casella = (chiave, etichetta, acceso, bloccata = false) =>
        _html`<label class="flex items-center gap-2 text-slate-300"><input type="checkbox" data-al-cambio="notificheScegli" data-args="${_args(chiave)}" data-argomento="spunta" ${acceso ? 'checked' : ''} ${bloccata ? 'disabled' : ''}><span>${etichetta}${bloccata ? ' — non si può silenziare' : ''}</span></label>`;
    const fissa = new Set(p.non_silenziabili || []);
    return _html`
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <fieldset class="space-y-1"><legend class="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Dove</legend>
                ${Object.entries(CANALI).map(([c, e]) => casella(`canale.${c}`, e, p.canali?.[c]))}
            </fieldset>
            <fieldset class="space-y-1"><legend class="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Cosa</legend>
                ${Object.entries(CATEGORIE).map(([c, e]) => casella(`categoria.${c}`, e, p.categorie?.[c], fissa.has(c)))}
            </fieldset>
            <fieldset class="space-y-1"><legend class="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Quando</legend>
                ${casella('silenzioso', 'Non disturbare (gli avvisi di sicurezza passano lo stesso)', p.silenzioso)}
            </fieldset>
        </div>`;
}

function _scrivi(html) {
    const el = $('notifiche-contenuto');
    if (!el) return;
    el.innerHTML = html;
    safeCreateIcons();
}

export async function caricaNotifiche() {
    if (!$('notifiche-contenuto')) return;
    _scrivi(_html`<p class="text-slate-500">Un momento…</p>`);
    let stato;
    try {
        stato = await _stato();
    } catch (errore) {
        console.error('caricaNotifiche:', errore);
        stato = { tipo: 'errore', motivo: String(errore.message || errore) };
    }
    if (MESSAGGI[stato.tipo])
        return _scrivi(
            _html`<p class="text-amber-300" data-stato="${stato.tipo}">${MESSAGGI[stato.tipo]}</p>`,
        );
    if (stato.tipo === 'errore') {
        return _scrivi(
            _html`<p class="text-rose-300" data-stato="errore">Non riesco a leggere le notifiche: ${stato.motivo}</p>`,
        );
    }

    let elenco = [];
    let preferenze = {};
    try {
        [{ dispositivi: elenco }, preferenze] = await Promise.all([
            _chiama('/api/notifiche/dispositivi'),
            _chiama('/api/notifiche/preferenze'),
        ]);
    } catch (errore) {
        return _scrivi(
            _html`<p class="text-rose-300" data-stato="errore">Non riesco a leggere le notifiche: ${errore.message}</p>`,
        );
    }

    const principale =
        stato.tipo === 'attive'
            ? _html`<p class="text-emerald-300" data-stato="attive">Attive su questo dispositivo.</p>
                <div class="flex flex-wrap gap-2">
                    <button type="button" data-gesto="notificheProva" class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold">Mandami una prova</button>
                    <button type="button" data-gesto="notificheDisattiva" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs">Disattiva su questo dispositivo</button>
                </div>`
            : _html`<p class="text-slate-300" data-stato="da_attivare">Questo dispositivo non riceve ancora gli avvisi.</p>
                <button type="button" data-gesto="notificheAttiva" class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold">Attiva le notifiche su questo dispositivo</button>`;

    _scrivi(_html`
        ${principale}
        <p id="notifiche-esito" role="status" class="text-[11px] text-slate-400 min-h-[1rem]"></p>
        <h4 class="text-[11px] uppercase tracking-wider text-slate-500 pt-1">Dispositivi iscritti (${elenco.length})</h4>
        ${_dispositivi(elenco)}
        <h4 class="text-[11px] uppercase tracking-wider text-slate-500 pt-2">Cosa vuoi sentire</h4>
        ${_preferenze(preferenze)}`);

    // Un'iscrizione che il browser ha e il server no (il database rifatto, il telefono tolto altrove) si rimette a
    // posto da sola: lo stesso indirizzo e' lo stesso telefono, non un secondo.
    if (stato.tipo === 'attive' && !elenco.length) await _consegna(stato.iscrizione).catch(() => {});
}

function _esito(testo, errore = false) {
    const el = $('notifiche-esito');
    if (!el) return;
    el.textContent = testo;
    el.className = `text-[11px] min-h-[1rem] ${errore ? 'text-rose-300' : 'text-slate-400'}`;
}

// ------------------------------------------------------------------ gesti

async function _consegna(iscrizione) {
    const chiavi = iscrizione.toJSON().keys || {};
    await _chiama('/api/notifiche/sottoscrivi', 'POST', {
        endpoint: iscrizione.endpoint,
        p256dh: chiavi.p256dh,
        auth: chiavi.auth,
        nome: _nomeDelDispositivo(),
    });
}

async function notificheAttiva() {
    try {
        // Il permesso si chiede qui, dentro il clic: da un'altra parte il browser lo ignora.
        const permesso = await Notification.requestPermission();
        if (permesso !== 'granted') {
            await caricaNotifiche();
            return _esito('Senza il permesso del browser le notifiche non possono arrivare.', true);
        }
        const { chiave } = await _chiama('/api/notifiche/chiave');
        const registrazione = await _registrazione();
        const iscrizione =
            (await registrazione.pushManager.getSubscription()) ||
            (await registrazione.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: _chiaveInByte(chiave),
            }));
        await _consegna(iscrizione);
        await caricaNotifiche();
        _esito('Fatto: ora puoi mandarti una prova.');
    } catch (errore) {
        console.error('notificheAttiva:', errore);
        _esito(`Non sono riuscita ad attivarle: ${errore.message}`, true);
    }
}

async function notificheDisattiva() {
    try {
        const iscrizione = await (await _registrazione()).pushManager.getSubscription();
        if (iscrizione) {
            await _chiama('/api/notifiche/dimentica', 'POST', { endpoint: iscrizione.endpoint });
            await iscrizione.unsubscribe();
        }
        await caricaNotifiche();
        _esito('Disattivate su questo dispositivo.');
    } catch (errore) {
        console.error('notificheDisattiva:', errore);
        _esito(`Non sono riuscita a disattivarle: ${errore.message}`, true);
    }
}

async function notificheProva() {
    try {
        const esito = await _chiama('/api/notifiche/prova', 'POST', {});
        _esito(
            esito.success
                ? 'Mandata: dovrebbe arrivare tra un istante.'
                : "Il server non l'ha potuta mandare a nessun dispositivo: controlla le preferenze qui sotto.",
            !esito.success,
        );
    } catch (errore) {
        _esito(`La prova non è partita: ${errore.message}`, true);
    }
}

async function notificheScegli(chiave, valore) {
    try {
        await _chiama('/api/notifiche/preferenze', 'POST', { chiave, valore: Boolean(valore) });
        _esito('Salvato.');
    } catch (errore) {
        // Una categoria non silenziabile il server la rifiuta e dice perche': si rimette a posto la casella.
        _esito(errore.message, true);
        await caricaNotifiche();
    }
}

Gesti.registra({
    notificheAttiva,
    notificheDisattiva,
    notificheProva,
    notificheScegli,
});
