// ==================== I LUOGHI (#342) ====================
// La casa principale, altre abitazioni, il lavoro. Si registrano con un gesto di chi e' sul posto: la geolocalizzazione
// del browser, oppure la posizione che Home Assistant conosce di un telefono. Le coordinate esatte non arrivano qui:
// il server le tiene e ci manda quelle arrotondate a circa un chilometro.
import { Gesti } from './gesti.js';
import { _html } from './sicurezza.js';
import { safeCreateIcons } from './avvio.js';
import { getAuthHeaders } from './accesso.js';

const TIPI = { abitazione: 'Abitazione', lavoro: 'Lavoro', altro: 'Altro' };

function _messaggio(testo, errore = false, id = 'luoghi-esito') {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = testo;
    el.className = `text-xs ${errore ? 'text-rose-400' : 'text-emerald-400'}`;
}

async function _detail(res) {
    const dati = await res.json().catch(() => ({}));
    return typeof dati.detail === 'string' ? dati.detail : `Errore ${res.status}`;
}

export async function caricaLuoghi() {
    caricaCandidati();
    caricaPosizione();
    const contenitore = document.getElementById('luoghi-elenco');
    if (!contenitore) return;
    try {
        const res = await fetch('/api/luoghi', { headers: getAuthHeaders() });
        if (!res.ok) {
            contenitore.innerHTML = _html`<p class="text-xs text-slate-500">${await _detail(res)}</p>`;
            return;
        }
        const { luoghi } = await res.json();
        if (!luoghi.length) {
            contenitore.innerHTML = _html`<p class="text-xs text-slate-500">Nessun luogo registrato. Vai nel posto che vuoi registrare e premi «Registra questo luogo».</p>`;
            return;
        }
        contenitore.innerHTML = _html`${luoghi.map(
            (l) => _html`
            <div class="flex items-center justify-between gap-2 p-2 rounded-lg bg-slate-900/60 border border-slate-700/60" data-luogo="${l.id}">
                <div class="min-w-0">
                    <p class="text-slate-200 truncate">${l.nome}${l.principale ? ' · principale' : ''}</p>
                    <p class="text-[11px] text-slate-500">${TIPI[l.tipo] || l.tipo}${l.citta ? ' · ' + l.citta : ''} · raggio ${l.raggio_m} m · ${l.origine === 'telefono' ? 'dal telefono' : 'dal browser (meno preciso)'}</p>
                </div>
                <button type="button" data-gesto="cancellaLuogo" data-testo="${l.id}" class="text-rose-400 hover:text-rose-300 p-1" title="Cancella il luogo e le sue coordinate">
                    <i data-lucide="trash-2" class="w-4 h-4"></i>
                </button>
            </div>`,
        )}`;
        safeCreateIcons();
    } catch (err) {
        contenitore.innerHTML = _html`<p class="text-xs text-rose-400">Non riesco a leggere i luoghi: ${err.message}</p>`;
    }
}

function _datiDelModulo() {
    return {
        nome: (document.getElementById('luogo-nome')?.value || '').trim(),
        tipo: document.getElementById('luogo-tipo')?.value || 'abitazione',
        citta: (document.getElementById('luogo-citta')?.value || '').trim(),
        principale: Boolean(document.getElementById('luogo-principale')?.checked),
    };
}

async function _invia(daPersona, corpo) {
    const body = JSON.stringify(corpo);
    const res = daPersona
        ? await fetch('/api/luoghi/da-persona', {
              method: 'POST',
              headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
              body,
          })
        : await fetch('/api/luoghi', {
              method: 'POST',
              headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
              body,
          });
    if (!res.ok) {
        _messaggio(await _detail(res), true);
        return false;
    }
    _messaggio('Luogo registrato.');
    const nome = document.getElementById('luogo-nome');
    if (nome) nome.value = '';
    await caricaLuoghi();
    return true;
}

/** Registra il luogo in cui ci si trova, con la posizione che il browser di QUESTO dispositivo conosce. */
function registraQuestoLuogo() {
    const dati = _datiDelModulo();
    if (!dati.nome) return _messaggio('Dai un nome al luogo.', true);
    if (!navigator.geolocation) return _messaggio('Questo browser non sa dove si trova.', true);
    _messaggio("Leggo la posizione… (il browser ti chiedera' il permesso)");
    navigator.geolocation.getCurrentPosition(
        (pos) =>
            _invia(false, {
                ...dati,
                latitudine: pos.coords.latitude,
                longitudine: pos.coords.longitude,
                precisione_m: Math.round(pos.coords.accuracy || 0) || null,
                origine: 'browser',
            }),
        (err) => _messaggio(`Posizione non letta: ${err.message || 'permesso negato'}`, true),
        { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
    );
}

/** Registra un luogo dalla posizione che Home Assistant conosce di un telefono o di una persona. */
async function registraDalTelefono() {
    const dati = _datiDelModulo();
    const entita = (document.getElementById('luogo-entita')?.value || '').trim();
    if (!dati.nome) return _messaggio('Dai un nome al luogo.', true);
    if (!entita) return _messaggio('Scegli il telefono o la persona da cui leggere la posizione.', true);
    await _invia(true, { ...dati, entita });
}

async function cancellaLuogo(id) {
    if (!id || !confirm('Cancellare il luogo e le sue coordinate?')) return;
    const res = await fetch(`/api/luoghi/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    if (!res.ok) return _messaggio(await _detail(res), true);
    _messaggio('Luogo cancellato.');
    await caricaLuoghi();
}

const MOTIVI_POSIZIONE = {
    non_in_home_assistant:
        'Home Assistant non conosce questo telefono: controlla di aver scelto quello giusto.',
    senza_coordinate:
        "Home Assistant non manda latitudine e longitudine: nell'app Home Assistant del telefono la posizione deve essere attiva.",
    troppo_vecchia: 'La posizione è ferma da troppo tempo (telefono spento o app chiusa?).',
    coordinate_illeggibili: 'La posizione che manda Home Assistant non è leggibile.',
};

function _distanza(metri) {
    return metri < 1000 ? `${metri} m` : `${(metri / 1000).toFixed(1).replace('.', ',')} km`;
}

function _fraseDellaPosizione(p) {
    if (p.stato === 'in_un_luogo') return `Adesso sei: ${p.luogo}.`;
    if (p.stato === 'spenta') return 'La tua posizione è spenta: scegli qui sotto il tuo telefono.';
    if (p.stato === 'in_giro') {
        const vicino = p.vicino
            ? ` Il luogo più vicino è «${p.vicino}», a circa ${_distanza(p.distanza_m || 0)}: se non è vero, il luogo è stato registrato nel punto sbagliato.`
            : '';
        return `Sei in giro: non in uno dei luoghi registrati.${vicino}`;
    }
    const ore = p.eta_minuti ? ` (ultimo aggiornamento ${Math.round(p.eta_minuti / 60)} ore fa)` : '';
    return `Non so dove sei adesso. ${MOTIVI_POSIZIONE[p.motivo] || ''}${p.motivo === 'troppo_vecchia' ? '' : ore}`.trim();
}

/** Riempie i due menu con le persone e i telefoni di Home Assistant, col nome che si legge. */
async function caricaCandidati() {
    const menu = ['luogo-entita', 'posizione-entita']
        .map((id) => document.getElementById(id))
        .filter(Boolean);
    if (!menu.length) return;
    try {
        const res = await fetch('/api/posizione/candidati', { headers: getAuthHeaders() });
        if (!res.ok) return;
        const { candidati } = await res.json();
        for (const m of menu) {
            const scelto = m.value;
            while (m.options.length > 1) m.remove(1);
            for (const c of candidati) {
                const voce = document.createElement('option');
                voce.value = c.entita;
                voce.textContent = c.ha_posizione ? c.nome : `${c.nome} (senza posizione)`;
                m.appendChild(voce);
            }
            if (!candidati.length) m.options[0].textContent = 'Home Assistant non ha persone o telefoni';
            m.value = scelto;
        }
    } catch {
        // il menu resta com'e': si puo' sempre riprovare riaprendo la scheda
    }
}

async function caricaPosizione() {
    const riga = document.getElementById('posizione-stato');
    if (!riga) return;
    try {
        const res = await fetch('/api/posizione/io', { headers: getAuthHeaders() });
        if (!res.ok) {
            riga.textContent = await _detail(res);
            return;
        }
        const p = await res.json();
        riga.textContent = _fraseDellaPosizione(p);
    } catch (err) {
        riga.textContent = `Non riesco a leggere la posizione: ${err.message}`;
    }
}

async function collegaLaMiaPosizione() {
    const entita = (document.getElementById('posizione-entita')?.value || '').trim();
    // Si collega appena si sceglie: niente secondo pulsante da dimenticare. Tornare sulla voce vuota non fa niente.
    if (!entita) return;
    const res = await fetch('/api/posizione/io', {
        method: 'PUT',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ entita }),
    });
    if (!res.ok) return _messaggio(await _detail(res), true, 'posizione-esito');
    _messaggio('Posizione collegata.', false, 'posizione-esito');
    await caricaPosizione();
}

async function spegniLaMiaPosizione() {
    const res = await fetch('/api/posizione/io', {
        method: 'PUT',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ entita: '' }),
    });
    if (!res.ok) return _messaggio(await _detail(res), true, 'posizione-esito');
    const campo = document.getElementById('posizione-entita');
    if (campo) campo.value = '';
    _messaggio('Posizione spenta.', false, 'posizione-esito');
    await caricaPosizione();
}

Gesti.registra({
    collegaLaMiaPosizione,
    spegniLaMiaPosizione,
    registraQuestoLuogo,
    registraDalTelefono,
    cancellaLuogo,
});
