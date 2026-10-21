// Quanto lavora il server di casa: tre barre (processore, memoria, disco) e la temperatura, dalla console.
//
// Chiede `/api/telemetria` ogni dieci secondi (e subito appena il pannello e' in vista), e solo se la scheda Console e' in vista e la pagina non e' nascosta: un tablet
// appeso al muro con un'altra scheda aperta non deve interrogare il server per un pannello che nessuno guarda. Se il server dice
// `disponibile: false` (un PC di sviluppo, senza `/proc`), o la richiesta fallisce, il pannello resta nascosto: niente numeri
// inventati e niente errore in faccia a chi non ha chiesto niente.
import { getAuthHeaders } from './accesso.js';

const OGNI_MS = 10_000;

function barra(id, percentuale, testo) {
    const riempimento = document.getElementById(id);
    const valore = document.getElementById(`${id}-valore`);
    if (!riempimento || !valore) return;
    const p = Number.isFinite(percentuale) ? Math.min(100, Math.max(0, percentuale)) : 0;
    riempimento.style.width = `${p}%`;
    riempimento.dataset.livello = p >= 90 ? 'alto' : p >= 70 ? 'medio' : 'basso';
    valore.textContent = testo;
}

function mostra(dati) {
    const pannello = document.getElementById('pannello-server');
    if (!pannello) return;
    if (!dati || dati.disponibile !== true) {
        pannello.hidden = true;
        return;
    }
    barra('server-cpu', dati.cpu, dati.cpu == null ? '–' : `${dati.cpu}%`);
    barra('server-memoria', dati.memoria?.percentuale, `${dati.memoria?.percentuale ?? '–'}%`);
    barra(
        'server-disco',
        dati.disco?.percentuale,
        dati.disco ? `${dati.disco.percentuale}% · ${dati.disco.libero_gb} GB liberi` : '–',
    );
    const caldo = document.getElementById('server-temperatura');
    if (caldo) caldo.textContent = dati.temperatura_c == null ? '' : `${dati.temperatura_c.toFixed(0)}°C`;
    pannello.hidden = false;
}

function inVista() {
    const pannello = document.getElementById('pannello-server');
    const scheda = document.getElementById('tab-console');
    return !document.hidden && !!pannello && !!scheda && scheda.getClientRects().length > 0;
}

let ultimaRichiesta = 0;

// Ogni secondo si guarda (senza rete) se il pannello e' in vista; la richiesta parte subito appena lo e', poi ogni dieci secondi.
// Cosi' tornare alla Console o entrare dopo l'accesso mostra i numeri subito, senza aspettare il prossimo giro.
async function aggiorna() {
    if (!inVista() || Date.now() - ultimaRichiesta < OGNI_MS) return;
    ultimaRichiesta = Date.now();
    try {
        const res = await fetch('/api/telemetria', { headers: getAuthHeaders() });
        mostra(res.ok ? await res.json() : null);
    } catch {
        mostra(null);
    }
}

setInterval(aggiorna, 1000);
document.addEventListener('visibilitychange', aggiorna);
