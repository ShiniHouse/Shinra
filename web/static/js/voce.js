// ==================== SPEECH RECOGNITION (COMPATIBILE IOS SAFARI / PWA) ====================
let activeRecognition = null;
let isRecording = false;

function stopRecording() {
    isRecording = false;
    const btn = document.getElementById('mic-btn');
    if (btn) btn.classList.remove('bg-rose-600', 'text-white', 'mic-active');
    const st = document.getElementById('recording-status');
    if (st) st.classList.add('hidden');
    updateLivingCoreState('idle');
}

// ---- Il microfono, dalla issue #31 ----
//
// Prima di questa versione qui c'era solo la Web Speech API, che manda
// l'audio ai server del produttore del browser: Google su Chrome, Apple
// su Safari. Ogni parola detta all'assistente usciva di casa, mentre il
// README prometteva «Zero Cloud per i Dati Privati».
//
// Adesso l'audio si registra e si manda al server, che lo trascrive con
// Whisper e non lo inoltra a nessuno. La Web Speech API resta
// raggiungibile mettendo `voce.motore: browser` in configurazione: e'
// una scelta, e la dashboard dice cosa comporta.

let statoVoce = null;
let registratore = null;

async function leggiStatoVoce() {
    // Si tiene da parte solo una risposta definitiva. Finche' il
    // modello si sta caricando, «non ancora pronto» e' vero adesso e
    // falso fra un minuto: ricordarselo vorrebbe dire un microfono
    // che resta spento fino al prossimo ricaricamento della pagina.
    if (statoVoce && (!statoVoce.in_casa || statoVoce.modello_caricato)) return statoVoce;
    try {
        const res = await fetch('/api/voce/stato', { headers: getAuthHeaders() });
        if (res.ok) statoVoce = await res.json();
    } catch (e) { console.warn('stato voce:', e); }
    return statoVoce;
}

async function toggleSpeechRecognition() {
    const stato = await leggiStatoVoce();

    // `in_casa` falso vuol dire che la configurazione ha scelto il
    // browser: si usa la vecchia strada, sapendo cosa comporta.
    if (stato && stato.in_casa) return toggleTrascrizioneLocale(stato);

    return toggleWebSpeech();
}

async function toggleTrascrizioneLocale(stato) {
    if (isRecording && registratore) {
        try { registratore.stop(); } catch {}
        return;
    }
    if (!stato.pronto) {
        // Meglio dirlo prima di registrare: chi preme e poi scopre che
        // non serviva a niente ha gia' parlato.
        alert(stato.spiegazione || 'Il riconoscimento vocale non e\' disponibile.');
        return;
    }
    if (!stato.modello_caricato) {
        // Stessa ragione del controllo qui sopra, un passo piu' in
        // la': il motore c'e', ma i pesi non sono ancora in memoria.
        // Registrare adesso vuol dire parlare dentro un'attesa che
        // finira' tagliata da qualunque proxy stia davanti al server.
        //
        // Il messaggio arriva dal server e non e' scritto qui, perche'
        // «sto preparando» e «ci ho provato e non ci sono riuscito»
        // sono due cose diverse e solo il server sa quale delle due.
        alert(stato.spiegazione_modello || 'Sto ancora preparando il modello di riconoscimento. Riprova fra un minuto.');
        return;
    }
    if (!navigator.mediaDevices || !window.MediaRecorder) {
        alert("Questo browser non sa registrare audio. Puoi digitare il tuo messaggio.");
        return;
    }

    let flusso;
    try {
        flusso = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
        alert("Accesso al microfono non consentito. Controlla i permessi del browser.");
        return;
    }

    const pezzi = [];
    registratore = new MediaRecorder(flusso);

    registratore.ondataavailable = e => { if (e.data && e.data.size) pezzi.push(e.data); };

    registratore.onstart = () => {
        isRecording = true;
        const btn = document.getElementById('mic-btn');
        if (btn) btn.classList.add('bg-rose-600', 'text-white', 'mic-active');
        const st = document.getElementById('recording-status');
        if (st) {
            st.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span> 🎙️ In ascolto... parla pure!';
            st.classList.remove('hidden');
        }
        updateLivingCoreState('listening');
    };

    registratore.onstop = async () => {
        // Il microfono si spegne davvero: senza questo, la spia di
        // registrazione del browser resta accesa dopo che si e' finito
        // di parlare, e non c'e' modo peggiore di far credere a
        // qualcuno che lo stai ascoltando sempre.
        flusso.getTracks().forEach(t => t.stop());
        stopRecording();

        const registrazione = new Blob(pezzi, { type: registratore.mimeType || 'audio/webm' });
        if (!registrazione.size) return;

        const st = document.getElementById('recording-status');
        if (st) {
            st.innerHTML = '<span class="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></span> Trascrivo...';
            st.classList.remove('hidden');
        }

        try {
            const modulo = new FormData();
            modulo.append('audio', registrazione, 'comando.webm');
            modulo.append('tipo', registratore.mimeType || 'audio/webm');

            const res = await fetch('/api/voce/trascrivi', {
                method: 'POST', headers: intestazioniPerModulo(), body: modulo
            });
            if (!res.ok) { alert(await _dettaglioErrore(res)); return; }

            const esito = await res.json();
            if (esito.vuota) {
                if (st) st.innerHTML = 'Non ho sentito niente.';
                setTimeout(() => { if (st) st.classList.add('hidden'); }, 2000);
                return;
            }

            const input = document.getElementById('user-input');
            if (input) { input.value = esito.testo; handleSend(); }
        } catch (e) {
            alert('Non sono riuscito a trascrivere: ' + ((e && e.message) || e));
        } finally {
            if (st) st.classList.add('hidden');
        }
    };

    registratore.start();
}

async function toggleWebSpeech() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        alert("Il riconoscimento vocale non è supportato in questa versione del browser. Puoi digitare il tuo messaggio.");
        return;
    }

    if (isRecording && activeRecognition) {
        try { activeRecognition.stop(); } catch {}
        stopRecording();
        return;
    }

    // Su iOS Safari PWA: sblocca la sessione microfono se necessario
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(t => t.stop());
        } catch (micErr) {
            console.warn('Permesso microfono non concesso da iOS:', micErr);
            alert("Accesso al microfono non consentito da iOS. Vai in Impostazioni iPhone ➔ Safari ➔ Microfono e seleziona 'Consenti'.");
            return;
        }
    }

    try {
        activeRecognition = new SpeechRec();
        activeRecognition.lang = 'it-IT';
        activeRecognition.continuous = false;
        activeRecognition.interimResults = true;
        activeRecognition.maxAlternatives = 1;

        let finalTranscript = '';

        activeRecognition.onstart = () => {
            isRecording = true;
            const btn = document.getElementById('mic-btn');
            if (btn) btn.classList.add('bg-rose-600', 'text-white', 'mic-active');
            const st = document.getElementById('recording-status');
            if (st) {
                st.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span> 🎙️ In ascolto... parla pure!';
                st.classList.remove('hidden');
            }
            updateLivingCoreState('listening');
        };

        activeRecognition.onresult = (event) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                const piece = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += piece;
                } else {
                    interim += piece;
                }
            }
            const display = (finalTranscript || interim).trim();
            const input = document.getElementById('user-input');
            if (input && display) {
                input.value = display;
            }
        };

        activeRecognition.onerror = (event) => {
            console.warn('SpeechRecognition error:', event.error);
            stopRecording();
            if (event.error === 'not-allowed') {
                alert("Permesso microfono non autorizzato su iOS. Controlla le impostazioni di Safari.");
            }
        };

        activeRecognition.onend = () => {
            stopRecording();
            const input = document.getElementById('user-input');
            if (input && input.value.trim().length > 0) {
                handleSend();
            }
        };

        activeRecognition.start();
    } catch (err) {
        console.error('Errore avvio SpeechRecognition:', err);
        stopRecording();
    }
}

// ==================== MOTORE VOCALE UMANIZZATO HD ====================
let neuralVoice = localStorage.getItem('shinra_neural_voice') || 'it-IT-DiegoNeural';
let voiceMuted = localStorage.getItem('shinra_voice_muted') === 'true';
let voiceRate = parseFloat(localStorage.getItem('shinra_voice_rate')) || 1.0;
let voicePitch = parseFloat(localStorage.getItem('shinra_voice_pitch')) || 1.0;
let selectedVoiceURI = localStorage.getItem('shinra_voice_uri') || 'auto';
let availableVoices = [];
let currentAudioPlayer = null;

function initVoiceEngine() {
    syncVoiceUI();
    if ('speechSynthesis' in window) {
        function loadBrowserVoices() {
            availableVoices = window.speechSynthesis.getVoices();
            populateVoiceSelect();
        }
        loadBrowserVoices();
        if (window.speechSynthesis.onvoiceschanged !== undefined) {
            window.speechSynthesis.onvoiceschanged = loadBrowserVoices;
        }
    }
}

function populateVoiceSelect() {
    const select = document.getElementById('cfg-browser-voice');
    if (!select) return;

    const itVoices = availableVoices.filter(v => v.lang.startsWith('it') || v.lang.startsWith('IT'));
    select.innerHTML = '<option value="auto">✨ Selezione Automatica Migliore (Naturale)</option>';

    itVoices.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.voiceURI;
        opt.textContent = `${v.name} (${v.lang})`;
        if (v.voiceURI === selectedVoiceURI) opt.selected = true;
        select.appendChild(opt);
    });
}

function syncVoiceUI() {
    // Settings tab
    const cfgNeural = document.getElementById('cfg-neural-voice');
    if (cfgNeural) cfgNeural.value = neuralVoice;

    const cfgMuted = document.getElementById('cfg-voice-muted');
    if (cfgMuted) cfgMuted.checked = voiceMuted;

    const cfgRate = document.getElementById('cfg-voice-rate');
    if (cfgRate) {
        cfgRate.value = voiceRate;
        const rVal = document.getElementById('rate-val');
        if (rVal) rVal.textContent = voiceRate + 'x';
    }

    const cfgPitch = document.getElementById('cfg-voice-pitch');
    if (cfgPitch) {
        cfgPitch.value = voicePitch;
        const pVal = document.getElementById('pitch-val');
        if (pVal) pVal.textContent = voicePitch;
    }
}

function setNeuralVoice(voiceId) {
    neuralVoice = voiceId;
    localStorage.setItem('shinra_neural_voice', voiceId);
    syncVoiceUI();
}

function toggleVoiceMute() {
    voiceMuted = !voiceMuted;
    localStorage.setItem('shinra_voice_muted', voiceMuted);
    if (voiceMuted) {
        if (currentAudioPlayer) {
            currentAudioPlayer.pause();
            currentAudioPlayer = null;
        }
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
    }
    syncVoiceUI();
}

function setSpecificVoice(uri) {
    selectedVoiceURI = uri;
    localStorage.setItem('shinra_voice_uri', uri);
}

function setVoiceRate(r) {
    voiceRate = parseFloat(r);
    localStorage.setItem('shinra_voice_rate', r);
    const rVal = document.getElementById('rate-val');
    if (rVal) rVal.textContent = r + 'x';
}

function setVoicePitch(p) {
    voicePitch = parseFloat(p);
    localStorage.setItem('shinra_voice_pitch', p);
    const pVal = document.getElementById('pitch-val');
    if (pVal) pVal.textContent = p;
}

function cleanTextForSpeech(text) {
    if (!text) return "";
    let clean = text
        .replace(/```[\s\S]*?```/g, '')
        .replace(/`.*?`/g, '')
        .replace(/https?:\/\/\S+/g, '')
        .replace(/[*_~#>[\]]/g, '')
        .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '')
        .replace(/\bHA\b/g, 'Home Assistant')
        .replace(/\bdegli alias\b/gi, 'degli alias')
        .replace(/\b°C\b/g, 'gradi')
        .replace(/\s+/g, ' ')
        .trim();
    return clean;
}

async function speakText(text) {
    if (voiceMuted) return;

    const clean = cleanTextForSpeech(text);
    if (!clean) return;

    updateLivingCoreState('speaking');

    // Se la voce selezionata è una voce neurale HD del server
    if (neuralVoice !== 'browser') {
        try {
            if (currentAudioPlayer) {
                currentAudioPlayer.pause();
                currentAudioPlayer = null;
            }
            const res = await fetch('/api/tts', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    text: clean,
                    voice: neuralVoice
                })
            });
            if (res.ok) {
                const blob = await res.blob();
                const audioUrl = URL.createObjectURL(blob);
                currentAudioPlayer = new Audio(audioUrl);
                currentAudioPlayer.onended = () => updateLivingCoreState('idle');
                currentAudioPlayer.onerror = () => updateLivingCoreState('idle');
                currentAudioPlayer.play().catch(e => {
                    console.warn('Audio playback block/error:', e);
                    updateLivingCoreState('idle');
                });
                return;
            }
        } catch (e) {
            console.warn('Fallback a sintesi browser per errore server TTS:', e);
        }
    }

    // Fallback locale Web Speech API
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(clean);
        utterance.lang = 'it-IT';
        if (selectedVoiceURI && selectedVoiceURI !== 'auto') {
            const specific = availableVoices.find(v => v.voiceURI === selectedVoiceURI || v.name === selectedVoiceURI);
            if (specific) utterance.voice = specific;
        }
        utterance.pitch = voicePitch;
        utterance.rate = voiceRate;
        utterance.onend = () => updateLivingCoreState('idle');
        utterance.onerror = () => updateLivingCoreState('idle');
        window.speechSynthesis.speak(utterance);
    } else {
        updateLivingCoreState('idle');
    }
}

async function testVoicePreview() {
    const previewText = neuralVoice.includes('Diego') || neuralVoice.includes('Giuseppe')
        ? "Sistemi operativi. Voce neurale ad alta definizione calibrata e pronta."
        : "Ciao, sono Shinra. La mia voce neurale ad alta definizione è pronta.";

    const wasMuted = voiceMuted;
    voiceMuted = false;
    await speakText(previewText);
    voiceMuted = wasMuted;
}
