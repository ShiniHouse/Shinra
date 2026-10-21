// Quanto lavora il server di casa: una pillola nell'intestazione, accanto a Ollama e Home Assistant.
//
// Chiede `/api/telemetria` ogni dieci secondi, e solo se la pagina non e' nascosta: un tablet con la schermata spenta non deve
// interrogare il server per una pillola che nessuno guarda. Se il server dice `disponibile: false` (un PC di sviluppo, senza
// `/proc`), o la richiesta fallisce, la pillola resta nascosta: niente numeri inventati e niente errore in faccia a chi non ha
// chiesto niente.
//
// Sta nell'intestazione e non nella colonna della console di proposito: quella colonna e' tenuta leggera da una misura
// (`test_la_colonna_della_console_resta_leggera`), e questo non e' cio' che succede in casa ma lo stato di un sistema, come gli
// altri due pallini.
import { getAuthHeaders } from './accesso.js';

const OGNI_MS = 10_000;

function livelloDi(percentuale) {
    return percentuale >= 90 ? 'alto' : percentuale >= 70 ? 'medio' : 'basso';
}

function mostra(dati) {
    const pillola = document.getElementById('server-chip');
    if (!pillola) return;
    if (!dati || dati.disponibile !== true) {
        pillola.style.display = 'none';
        return;
    }
    const cpu = Number.isFinite(dati.cpu) ? dati.cpu : null;
    const memoria = dati.memoria?.percentuale ?? null;
    const disco = dati.disco?.percentuale ?? null;
    const valori = [cpu, memoria, disco].filter((v) => v !== null);
    pillola.dataset.livello = livelloDi(Math.max(0, ...valori));
    document.getElementById('server-testo').textContent = cpu === null ? 'Server' : `CPU ${cpu}%`;
    const righe = [
        cpu === null ? null : `Processore ${cpu}%`,
        memoria === null ? null : `Memoria ${memoria}%`,
        disco === null
            ? null
            : `Disco ${disco}%${dati.disco.libero_gb != null ? ` (${dati.disco.libero_gb} GB liberi)` : ''}`,
        Number.isFinite(dati.temperatura_c) ? `Temperatura ${dati.temperatura_c.toFixed(0)}°C` : null,
    ].filter(Boolean);
    pillola.title = `Il server: ${righe.join(' · ')}`;
    pillola.style.display = 'flex';
}

let ultimaRichiesta = 0;

// Ogni secondo si guarda (senza rete) se la pagina e' in vista; la richiesta parte subito appena lo e', poi ogni dieci secondi.
async function aggiorna() {
    if (document.hidden || !document.getElementById('server-chip') || Date.now() - ultimaRichiesta < OGNI_MS)
        return;
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
