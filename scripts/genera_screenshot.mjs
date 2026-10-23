// Rifa le schermate della documentazione (docs/screenshots/) dall'anteprima statica della dashboard, con **dati di esempio**.
//
//   python scripts/anteprima.py
//   PYTHONPATH=src python -c "from jinja2 import Environment, FileSystemLoader as F; open('.anteprima/accesso.html','w',encoding='utf-8').write(Environment(loader=F('web/templates')).get_template('accesso.html').render(nome_assistente='Shinra'))"
//   python -m http.server 8899 --directory .anteprima --bind 127.0.0.1 &
//   PLAYWRIGHT_CHANNEL=chrome node scripts/genera_screenshot.mjs
//
// Non parla con una casa vera: ogni risposta del server e' finta (una famiglia di esempio, una casa di esempio), cosi' le immagini non portano
// nomi, orari o dispositivi di nessuno e si possono rifare a ogni versione con lo stesso risultato. Le immagini della dashboard sono quelle della
// vera interfaccia, la stessa che gira in casa: cambiano solo i dati. Con `ANTEPRIMA=http://...` si cambia l'indirizzo.
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const BASE = process.env.ANTEPRIMA || 'http://127.0.0.1:8899';
const USCITA = 'docs/screenshots';
mkdirSync(USCITA, { recursive: true });

const json = (corpo) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(corpo) });

// ------------------------------------------------------------------ una casa di esempio per il grafo del Cervello
function casaDiEsempio() {
    const nodi = [];
    const fili = [];
    const nodo = (id, tipo, nome, cluster, extra = {}) => nodi.push({ id, tipo, nome, cluster, ...extra });
    const filo = (da, a, tipo) => fili.push({ da, a, tipo });
    const stanze = ['Cucina', 'Salotto', 'Camera', 'Studio', 'Bagno', 'Ingresso'];
    stanze.forEach((s) => nodo(`stanza:${s}`, 'stanza', s, 'stanze'));
    const dispositivi = [];
    stanze.forEach((s, i) => {
        for (const [tipo, etichetta] of [['light', 'luce'], ['cover', 'tapparella'], ['climate', 'clima']].slice(0, 2 + (i % 2))) {
            const id = `${tipo}.${s.toLowerCase()}`;
            dispositivi.push(id);
            nodo(`dispositivo:${id}`, 'dispositivo', `${etichetta} ${s.toLowerCase()}`, 'dispositivi');
            filo(`dispositivo:${id}`, `stanza:${s}`, 'sta_in');
            nodo(`alias:${id}`, 'alias', `${etichetta} ${s.toLowerCase()}`, 'alias');
            filo(`alias:${id}`, `dispositivo:${id}`, 'chiama');
        }
    });
    ['Buongiorno', 'Buonanotte', 'Cinema', 'Lavoro', 'Studio'].forEach((r, i) => {
        nodo(`routine:${r}`, 'routine', r, 'routine', { stato: 'attivo' });
        for (let k = 0; k < 3; k++) filo(`routine:${r}`, `dispositivo:${dispositivi[(i * 3 + k * 2) % dispositivi.length]}`, 'comanda');
    });
    ['Luce cucina al mattino', 'Tapparelle al tramonto', 'Clima notturno', 'Avviso porta aperta'].forEach((r, i) => {
        nodo(`regola:${r}`, 'regola', r, 'regole', { stato: 'attivo' });
        filo(`regola:${r}`, `dispositivo:${dispositivi[(i * 5) % dispositivi.length]}`, 'comanda');
    });
    const argomenti = ['famiglia', 'casa', 'abitudini', 'animali', 'lavoro'];
    argomenti.forEach((a) => nodo(`argomento:${a}`, 'argomento', a, 'conoscenza'));
    for (let i = 0; i < 28; i++) {
        nodo(`fatto:${i}`, 'fatto', `ricordo ${i + 1}`, 'conoscenza', { stato: 'attivo' });
        filo(`fatto:${i}`, `argomento:${argomenti[i % argomenti.length]}`, 'riguarda');
    }
    const strumenti = ['control_device', 'comanda_clima', 'comanda_tapparella', 'get_weather', 'add_reminder', 'get_latest_news', 'stato_aperture'];
    strumenti.forEach((s) => nodo(`strumento:${s}`, 'strumento', s, 'strumenti'));
    ['casa', 'clima e tapparelle', 'agenda', 'informazioni', 'energia'].forEach((d, i) => {
        nodo(`agente:${d}`, 'agente', `agente ${d}`, 'agenti');
        for (const s of strumenti.slice(i, i + 2)) filo(`agente:${d}`, `strumento:${s}`, 'usa');
    });
    nodo('agente:modello', 'agente', 'modello', 'agenti');
    const conta = (c) => nodi.filter((n) => n.cluster === c).length;
    const nomi = { stanze: 'Stanze', routine: 'Routine', regole: 'Regole', dispositivi: 'Dispositivi', alias: 'Alias', strumenti: 'Strumenti', agenti: 'Agenti', conoscenza: 'Conoscenza' };
    return {
        nodi,
        collegamenti: fili,
        clusters: Object.entries(nomi).map(([id, nome]) => ({ id, nome, nodi: conta(id), nascosti: 0 })),
        sistemi: [
            { id: 'home_assistant', nome: 'Home Assistant', cluster: 'dispositivi', stato: 'attivo', motivo: '' },
            { id: 'modello', nome: 'Modello', cluster: 'agenti', stato: 'attivo', motivo: '' },
            { id: 'regole', nome: 'Regole', cluster: 'regole', stato: 'attivo', motivo: '' },
            { id: 'notizie', nome: 'Notizie', cluster: 'strumenti', stato: 'attivo', motivo: '' },
        ],
        contatori: { nodi: nodi.length, collegamenti: fili.length, sistemi: 4, sistemi_attivi: 4, agenti_pronti: 6 },
        troncato: false,
    };
}

// ------------------------------------------------------------------ le risposte finte del server
const DOMANI = new Date(Date.now() + 24 * 3600 * 1000);
DOMANI.setHours(7, 30, 0, 0);

async function fingiIlServer(pagina) {
    const grafo = casaDiEsempio();
    const rotte = {
        '**/api/status': json({ ollama: { status: 'online', active_model: 'qwen2.5:3b' }, home_assistant: { status: 'ok' } }),
        '**/api/auth/status': json({ auth_enabled: true, authenticated: true, protect_dashboard: true }),
        '**/api/users': json([
            { id: 'alessio', name: 'Alessio', role: 'admin', age_group: 'adult' },
            { id: 'sonia', name: 'Sonia', role: 'adult', age_group: 'adult' },
        ]),
        '**/api/telemetria': json({ disponibile: true, cpu: 31, memoria: { percentuale: 58, usata_mb: 9100, totale_mb: 15800 }, disco: { percentuale: 51, libero_gb: 50.9 }, carico: 0.5, temperatura_c: 41 }),
        '**/api/presenza': json({ conosciuta: true, presenti: ['person.alessio'], in_attesa: [], abitata: true }),
        '**/api/timers': json([{ id: 't1', label: 'Pasta', remaining_seconds: 412, duration_seconds: 540 }]),
        '**/api/reminders': json([]),
        '**/api/regole': json({
            regole: [
                { id: 'r1', nome: 'Luce cucina al mattino', attiva: true, trigger: { tipo: 'orario', ora: '07:30' }, azioni: [], descrizione: 'Ogni giorno alle 07:30: accende la luce della cucina', prossimo: DOMANI.toISOString(), aspetta_un_evento: false, avviso: null },
            ],
        }),
        '**/api/modes': json([
            { id: 'm1', name: 'Buonanotte', description: 'Spegne le luci e chiude le tapparelle', trigger_phrases: ['buonanotte', 'vado a dormire'], actions: [{ type: 'ha_device', entity_id: 'light.salotto', action: 'turn_off' }, { type: 'ha_device', entity_id: 'cover.camera', action: 'close_cover' }, { type: 'delay', seconds: 5 }] },
            { id: 'm2', name: 'Cinema', description: 'Luci basse e tapparelle chiuse', trigger_phrases: ['modalità cinema', 'mettiamo su un film'], actions: [{ type: 'ha_device', entity_id: 'light.salotto', action: 'turn_off' }, { type: 'ha_device', entity_id: 'cover.salotto', action: 'close_cover' }] },
            { id: 'm3', name: 'Buongiorno', description: 'Apre le tapparelle e accende la luce della cucina', trigger_phrases: ['buongiorno'], actions: [{ type: 'ha_device', entity_id: 'cover.camera', action: 'open_cover' }, { type: 'ha_device', entity_id: 'light.cucina', action: 'turn_on' }] },
        ]),
        '**/api/cervello': json(grafo),
        '**/api/lavori': json({
            lavori: [
                { id: 'l_1', scopo: 'chat', richiesta: 'prepara la casa per la sera: tapparelle, luci, clima e una sveglia', stato: 'in_corso', avanzamento: 45, fase: 'consulto la casa', esito: '', motivo: '', creato_il: '2026-10-22T20:00:00', finito_il: null },
                { id: 'l_0', scopo: 'chat', richiesta: 'riassumi le notizie di tecnologia di oggi', stato: 'fatto', avanzamento: 100, fase: '', esito: 'Fatto.', motivo: '', creato_il: '2026-10-22T19:40:00', finito_il: '2026-10-22T19:41:10' },
            ],
        }),
    };
    for (const [percorso, risposta] of Object.entries(rotte)) await pagina.route(percorso, (r) => r.fulfill(risposta));
    await pagina.route('**/api/chat', (r) => {
        const frase = (r.request().postDataJSON() || {}).message || '';
        const risposte = {
            acquario: 'Fatto: la luce dell\'acquario è spenta. Domani a Capolona sarà sereno, minima 11°, massima 22°.',
            pane: 'Va bene: ti ricorderò di comprare il pane domani mattina.',
        };
        const chiave = Object.keys(risposte).find((k) => frase.includes(k));
        return r.fulfill(json({ response: risposte[chiave] || 'Fatto.', actions: chiave === 'acquario' ? [{ tool: 'control_device', args: {}, result: {} }] : [] }));
    });
    return grafo;
}

async function scrivi(pagina, domanda) {
    await pagina.locator('#user-input').fill(domanda);
    await pagina.locator('#send-btn').click();
    await pagina.waitForTimeout(900);
}

const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });

// ---------------------------------------------------------------- il computer
{
    const contesto = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
    const pagina = await contesto.newPage();
    await fingiIlServer(pagina);
    await pagina.goto(`${BASE}/index.html`);
    await pagina.waitForTimeout(2500);
    await scrivi(pagina, "spegni la luce dell'acquario e dimmi che tempo fa domani");
    await scrivi(pagina, 'ricordami di comprare il pane');
    await pagina.waitForTimeout(1500);
    await pagina.screenshot({ path: `${USCITA}/home-computer.png` });

    await pagina.goto(`${BASE}/index.html?scheda=automazioni`);
    await pagina.locator('#tab-automazioni').waitFor({ state: 'visible' });
    await pagina.waitForTimeout(1800);
    await pagina.screenshot({ path: `${USCITA}/automazioni-computer.png` });

    await pagina.goto(`${BASE}/index.html?scheda=cervello`);
    await pagina.locator('#tab-cervello').waitFor({ state: 'visible' });
    await pagina.waitForTimeout(7000); // la fisica si assesta
    await pagina.evaluate(async () => {
        const { attivita } = await import('/static/js/cervello_attivita.js');
        attivita.registra({ tipo: 'agente.richiesta', dati: { nodi: ['agente:modello'], richiesta: 'r1' } });
        attivita.registra({ tipo: 'agente.skill', dati: { nodi: ['strumento:control_device'], richiesta: 'r1' } });
        attivita.registra({ tipo: 'agente.dispositivo', dati: { nodi: ['dispositivo:light.cucina'], richiesta: 'r1', riuscito: true } });
    });
    await pagina.waitForTimeout(900);
    await pagina.screenshot({ path: `${USCITA}/cervello-computer.png` });
    await contesto.close();
}

// ---------------------------------------------------------------- il telefono
{
    const contesto = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const pagina = await contesto.newPage();
    await fingiIlServer(pagina);
    await pagina.goto(`${BASE}/index.html`);
    await pagina.waitForTimeout(2500);
    await scrivi(pagina, 'ricordami di comprare il pane');
    await pagina.waitForTimeout(1200);
    await pagina.screenshot({ path: `${USCITA}/home-telefono.png` });

    await pagina.evaluate(() => document.getElementById('mobile-menu-drawer').classList.remove('hidden'));
    await pagina.waitForTimeout(600);
    await pagina.screenshot({ path: `${USCITA}/menu-telefono.png` });

    await pagina.goto(`${BASE}/index.html?scheda=cervello`);
    await pagina.locator('#tab-cervello').waitFor({ state: 'visible' });
    await pagina.waitForTimeout(6000);
    await pagina.locator('#cervello-contenitore').scrollIntoViewIfNeeded();
    await pagina.evaluate(() => window.scrollBy(0, -90));
    await pagina.waitForTimeout(800);
    await pagina.screenshot({ path: `${USCITA}/cervello-telefono.png` });

    // La pagina del PIN (e' una pagina a parte, senza la dashboard): due profili, e poi il campo del PIN.
    await pagina.route('**/api/auth/profili', (r) => r.fulfill(json([{ id: 'alessio', name: 'Alessio', ha_pin: true }])));
    await pagina.route('**/api/auth/passkey/stato', (r) => r.fulfill(json({ disponibile: false })));
    await pagina.goto(`${BASE}/accesso.html`);
    await pagina.waitForTimeout(800);
    await pagina.locator('#pin').fill('1234');
    await pagina.waitForTimeout(300);
    await pagina.screenshot({ path: `${USCITA}/accesso-telefono.png` });
    await contesto.close();
}

await browser.close();
console.log('Schermate rifatte in', USCITA);
