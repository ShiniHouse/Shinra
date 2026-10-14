// ==================== I LUOGHI (#342) ====================
// La casa principale, altre abitazioni, il lavoro. Si registrano con un gesto di chi e' sul posto: la geolocalizzazione
// del browser, oppure la posizione che Home Assistant conosce di un telefono. Le coordinate esatte non arrivano qui:
// il server le tiene e ci manda quelle arrotondate a circa un chilometro.
import { Gesti } from './gesti.js';
import { _html } from './sicurezza.js';
import { safeCreateIcons } from './avvio.js';
import { getAuthHeaders } from './accesso.js';

const TIPI = { abitazione: 'Abitazione', lavoro: 'Lavoro', altro: 'Altro' };

function _messaggio(testo, errore = false) {
    const el = document.getElementById('luoghi-esito');
    if (!el) return;
    el.textContent = testo;
    el.className = `text-xs ${errore ? 'text-rose-400' : 'text-emerald-400'}`;
}

async function _detail(res) {
    const dati = await res.json().catch(() => ({}));
    return typeof dati.detail === 'string' ? dati.detail : `Errore ${res.status}`;
}

export async function caricaLuoghi() {
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

async function _invia(percorso, corpo) {
    const res = await fetch(`/api/luoghi${percorso}`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(corpo),
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
export function registraQuestoLuogo() {
    const dati = _datiDelModulo();
    if (!dati.nome) return _messaggio('Dai un nome al luogo.', true);
    if (!navigator.geolocation) return _messaggio('Questo browser non sa dove si trova.', true);
    _messaggio("Leggo la posizione… (il browser ti chiedera' il permesso)");
    navigator.geolocation.getCurrentPosition(
        (pos) =>
            _invia('', {
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
export async function registraDalTelefono() {
    const dati = _datiDelModulo();
    const entita = (document.getElementById('luogo-entita')?.value || '').trim();
    if (!dati.nome) return _messaggio('Dai un nome al luogo.', true);
    if (!entita) return _messaggio("Scrivi l'entita' del telefono (es. person.alessio).", true);
    await _invia('/da-persona', { ...dati, entita });
}

export async function cancellaLuogo(id) {
    if (!id || !confirm('Cancellare il luogo e le sue coordinate?')) return;
    const res = await fetch(`/api/luoghi/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    if (!res.ok) return _messaggio(await _detail(res), true);
    _messaggio('Luogo cancellato.');
    await caricaLuoghi();
}

Gesti.registra({ registraQuestoLuogo, registraDalTelefono, cancellaLuogo });
