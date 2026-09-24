// ==================== PASSKEY (issue #48) ====================
//
// Le proprie, non quelle di casa: una passkey e' personale come un
// dispositivo fidato. WebAuthn scambia byte e JSON scambia stringhe,
// quindi tutto passa da base64url — con i trattini al posto di piu' e
// barra, e senza riempimento. Sbagliare dialetto di base64 e' il modo
// piu' comune di far fallire una passkey senza capire perche'.

function _daBase64url(testo) {
    const normale = testo.replace(/-/g, '+').replace(/_/g, '/');
    const grezzo = atob(normale + '='.repeat((4 - (normale.length % 4)) % 4));
    return Uint8Array.from(grezzo, (c) => c.charCodeAt(0));
}

function _aBase64url(buffer) {
    let grezzo = '';
    for (const b of new Uint8Array(buffer)) grezzo += String.fromCharCode(b);
    return btoa(grezzo).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function loadPasskey() {
    const container = document.getElementById('passkey-lista');
    if (!container) return;

    let stato = { disponibile: false, spiegazione: '' };
    try {
        const res = await fetch('/api/auth/passkey/stato', { headers: getAuthHeaders() });
        if (res.ok) stato = await res.json();
    } catch (e) {
        console.error('stato passkey:', e);
    }

    const puo = stato.disponibile && !!window.PublicKeyCredential;
    const bottone = document.getElementById('btn-aggiungi-passkey');
    if (bottone) bottone.style.display = puo ? 'flex' : 'none';

    const nota = document.getElementById('passkey-nota');
    // La spiegazione del server dice *perche'* non si puo' e cosa
    // fare: un pulsante assente senza motivo sembra una funzione
    // rotta, non una funzione non disponibile qui.
    if (nota) nota.textContent = puo ? '' : stato.spiegazione || 'Non disponibili su questo dispositivo.';

    let elenco = [];
    try {
        const res = await fetch('/api/auth/passkey', { headers: getAuthHeaders() });
        if (res.ok) elenco = await res.json();
    } catch (e) {
        console.error('loadPasskey:', e);
    }

    if (!elenco.length) {
        container.innerHTML = _html`<div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400">
            Nessuna passkey. Il PIN continua a funzionare: le passkey lo affiancano, non lo sostituiscono.
        </div>`;
        return;
    }

    container.innerHTML = _html`${elenco.map(
        (p) => _html`
        <div class="p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800 flex items-center justify-between gap-3">
            <div class="flex items-center gap-3 min-w-0">
                <div class="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                    <i data-lucide="fingerprint" class="w-4 h-4 text-slate-400"></i>
                </div>
                <div class="min-w-0">
                    <h4 class="font-bold text-xs text-slate-100 truncate">${p.nome}</h4>
                    <p class="text-[10px] text-slate-500 truncate">
                        aggiunta ${_quando(p.creata_il)} · ultimo accesso ${_quando(p.ultimo_uso)}${p.tipo_dispositivo === 'multi_device' ? ' · sincronizzata' : ''}
                    </p>
                </div>
            </div>
            <button onclick="revocaPasskey(${_grezzo(_perAttributoJs(encodeURIComponent(p.id)))}, ${_grezzo(_perAttributoJs(p.nome))})" class="px-2.5 py-1 rounded-xl bg-slate-800 hover:bg-rose-600 border border-slate-700 hover:border-rose-500 text-[11px] text-slate-300 hover:text-white font-semibold shrink-0 transition">
                Revoca
            </button>
        </div>`,
    )}`;
    safeCreateIcons();
}

function _nomeDispositivo() {
    const ua = navigator.userAgent || '';
    if (/iPhone/i.test(ua)) return 'iPhone';
    if (/iPad/i.test(ua)) return 'iPad';
    if (/Android/i.test(ua)) return /Mobile/i.test(ua) ? 'Telefono Android' : 'Tablet Android';
    if (/Macintosh/i.test(ua)) return 'Mac';
    if (/Windows/i.test(ua)) return 'Computer Windows';
    if (/Linux/i.test(ua)) return 'Computer Linux';
    return 'Dispositivo';
}

async function aggiungiPasskey() {
    try {
        const avvio = await fetch('/api/auth/passkey/registrazione/inizio', {
            method: 'POST',
            headers: getAuthHeaders(),
        });
        if (!avvio.ok) {
            alert(await _dettaglioErrore(avvio));
            return;
        }
        const { sfida_id, opzioni } = await avvio.json();

        opzioni.challenge = _daBase64url(opzioni.challenge);
        opzioni.user.id = _daBase64url(opzioni.user.id);
        for (const c of opzioni.excludeCredentials || []) c.id = _daBase64url(c.id);

        const credenziale = await navigator.credentials.create({ publicKey: opzioni });
        if (!credenziale) return;

        const fine = await fetch('/api/auth/passkey/registrazione/fine', {
            method: 'POST',
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sfida_id: sfida_id,
                nome: _nomeDispositivo(),
                credenziale: {
                    id: credenziale.id,
                    rawId: _aBase64url(credenziale.rawId),
                    type: credenziale.type,
                    response: {
                        clientDataJSON: _aBase64url(credenziale.response.clientDataJSON),
                        attestationObject: _aBase64url(credenziale.response.attestationObject),
                    },
                },
            }),
        });
        if (!fine.ok) {
            alert(await _dettaglioErrore(fine));
            return;
        }
    } catch (e) {
        // Chi annulla il riconoscimento non ha sbagliato niente.
        if (e && (e.name === 'NotAllowedError' || e.name === 'AbortError')) return;
        if (e && e.name === 'InvalidStateError') {
            alert("Questo dispositivo ha gia' una passkey per il tuo profilo.");
            return;
        }
        alert('Non sono riuscito ad aggiungere la passkey: ' + ((e && e.message) || e));
        return;
    }
    await loadPasskey();
}

async function revocaPasskey(identificativo, nome) {
    if (!confirm(`Revocare «${nome}»?\n\nQuel dispositivo tornera' a chiedere il PIN.`)) return;

    const res = await fetch(`/api/auth/passkey/${identificativo}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    if (!res.ok) {
        alert(await _dettaglioErrore(res));
        return;
    }
    await loadPasskey();
}

// ==================== VOCI RICONOSCIUTE (issue #48) ====================
//
// Una voce non associata non e' un dettaglio estetico: comanda con i
// permessi di un ospite. Questo elenco esiste perche' associarla non
// richieda di copiare a mano un identificativo opaco letto in un log.

async function loadVoci() {
    const container = document.getElementById('voci-lista');
    if (!container) return;

    let elenco = [];
    try {
        const res = await fetch('/api/voci', { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(await _dettaglioErrore(res));
        elenco = await res.json();
    } catch (e) {
        console.error('loadVoci error:', e);
        container.innerHTML = _html`<div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 text-xs text-rose-300">Impossibile leggere le voci sentite.</div>`;
        return;
    }

    if (!elenco.length) {
        container.innerHTML = _html`<div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400">
            Nessuna voce sentita. Ne compare una qui quando qualcuno parla a un Echo e i profili vocali di Alexa sono configurati.
        </div>`;
        return;
    }

    const puoAssociare = posso('utenti.gestisci');
    const opzioni = (utente) =>
        Stato.utenti.map(
            (u) =>
                _html`<option value="${u.id}"${u.id === utente ? _grezzo(' selected') : ''}>${u.name}</option>`,
        );

    container.innerHTML = _html`${elenco.map((v) => {
        const noto = !!v.user_id;
        return _html`
        <div class="p-3.5 rounded-2xl bg-slate-900/60 border ${noto ? 'border-slate-800' : 'border-amber-700/50'} flex items-center justify-between gap-3">
            <div class="flex items-center gap-3 min-w-0">
                <div class="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                    <i data-lucide="${noto ? 'user-check' : 'user-x'}" class="w-4 h-4 ${noto ? 'text-slate-400' : 'text-amber-400'}"></i>
                </div>
                <div class="min-w-0">
                    <h4 class="font-bold text-xs text-slate-100 truncate">
                        ${noto ? v.nome_profilo : 'Voce non associata'}
                    </h4>
                    <p class="text-[10px] text-slate-500 truncate">
                        ${v.quante_volte} richieste · ultima ${_quando(v.ultima_volta)}${noto ? '' : ' · comanda come un ospite'}
                    </p>
                </div>
            </div>
            ${
                puoAssociare
                    ? _html`
            <div class="flex items-center gap-1.5 shrink-0">
                <select onchange="associaVoce(${_grezzo(_perAttributoJs(encodeURIComponent(v.person_id)))}, this.value)" class="px-2 py-1 rounded-xl bg-slate-800 border border-slate-700 text-[11px] text-slate-200">
                    <option value=""${noto ? '' : _grezzo(' selected')}>— nessuno —</option>
                    ${opzioni(v.user_id)}
                </select>
                <button onclick="dimenticaVoce(${_grezzo(_perAttributoJs(encodeURIComponent(v.person_id)))})" class="px-2.5 py-1 rounded-xl bg-slate-800 hover:bg-rose-600 border border-slate-700 hover:border-rose-500 text-[11px] text-slate-300 hover:text-white font-semibold transition">
                    Dimentica
                </button>
            </div>`
                    : ''
            }
        </div>`;
    })}`;
    safeCreateIcons();
}

async function associaVoce(personId, userId) {
    const res = await fetch('/api/voci/associa', {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ person_id: decodeURIComponent(personId), user_id: userId || null }),
    });
    if (!res.ok) {
        alert(await _dettaglioErrore(res));
    }
    await loadVoci();
}

async function dimenticaVoce(personId) {
    // Dimenticare non e' revocare: se quella voce parla ancora, la riga
    // ricompare — sconosciuta, senza permessi.
    if (!confirm('Dimenticare questa voce?\n\nSe parla di nuovo ricompare qui, senza permessi.')) return;

    const res = await fetch(`/api/voci/${personId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    if (!res.ok) {
        alert(await _dettaglioErrore(res));
        return;
    }
    await loadVoci();
}

// I gesti che il markup di quest'area puo' chiedere (#34). L'elenco e'
// la stessa forma che avra' la lista di `export` il giorno dei moduli.
Gesti.registra({
    aggiungiPasskey,
});
