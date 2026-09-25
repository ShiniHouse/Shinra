# 0007 — La parola di attivazione si ascolta nel browser

- **Stato:** Accettato
- **Data:** 2026-09-25
- **Attuazione:** milestone `v0.5.0`, issue #30

## Contesto

Non esiste alcuna parola di attivazione: per parlare con Shinra bisogna
premere il pulsante del microfono o passare da Alexa. La scheda della #30
lasciava aperta una domanda — «resta da decidere **dove** gira il
riconoscimento» — e quella domanda blocca tutto il resto, perche' cambia il
linguaggio, il modo di misurare e quale criterio di accettazione si ottiene
gratis.

Le due strade erano: **openWakeWord in Python**, con un microfono attaccato al
server; oppure **gli stessi modelli ONNX dentro la pagina**, sul dispositivo
che sta nella stanza.

Cio' che esiste gia': la #31 ha costruito la strada dell'audio — la dashboard
registra, manda al **proprio** server, e Whisper trascrive in casa. La #33 ha
dato a ogni punto di ascolto la coscienza di **dove si trova**, cosi' che fra
tre dispositivi svegliati dalla stessa parola risponda solo il piu' vicino.
Manca solo chi preme il pulsante al posto di una mano.

## Decisione

**Nel browser**, su un tablet o un telefono nella stanza. I tre modelli ONNX
di openWakeWord — melspettrogramma, embedding, parola — girano nella pagina
con onnxruntime-web, sul backend WASM.

La ragione che decide e' un criterio di accettazione della scheda:

> l'audio prima dell'attivazione non lascia mai il dispositivo

Nel browser questo e' vero **per costruzione**, non per promessa: la pagina
non manda niente finche' non ha sentito la parola, e non c'e' nessun percorso
di rete da fidarsi. Con un microfono sul server lo stesso criterio diventa
«non esce di casa», che e' un'altra cosa e piu' debole — l'audio continuo di
una stanza finirebbe comunque, di continuo, dentro un processo che sta
altrove.

La seconda ragione e' che il dispositivo c'e' gia'. Un tablet appoggiato in
cucina e' hardware che non si compra, e la dashboard e' gia' una PWA fatta per
stare li'.

## Conseguenze

**Positive.** Il criterio sulla privacy e' soddisfatto dalla struttura, non da
una riga di configurazione che qualcuno puo' cambiare. Ogni punto di ascolto
e' indipendente: se il tablet della cucina e' spento, il resto della casa
funziona. E la soglia si taglia **per dispositivo**, il che e' giusto — il
microfono di un tablet in cucina e quello di un telefono in camera non
sentono la stessa stanza.

**Negative, e vanno dette.** Una scheda del browser che ascolta e' una scheda
che deve restare **in primo piano e con lo schermo acceso**: i browser dei
telefoni sospendono o strozzano le schede in secondo piano, e iOS interrompe
la cattura quando si blocca lo schermo. Quindi il modo vero di usarla e' un
tablet su un supporto, attaccato alla corrente, con la PWA installata e lo
schermo acceso. Non e' un dettaglio di installazione: e' *il* vincolo di
questa scelta, e chi si aspetta un altoparlante da mettere su una mensola
restera' deluso.

Si tengono i calcoli sul thread dell'audio (`AudioWorklet`) e non su quello
principale: e' cio' che rende il riconoscimento meno sensibile allo
strozzamento del browser. La GPU non e' una strada — le operazioni audio di
questi modelli non hanno un'implementazione WebGL, e il backend cade su WASM.

**Da definire.** Se i modelli vadano messi dentro il repository o presi da un
CDN al primo caricamento: sono file binari, e l'ADR 0006 dice che il codice
servito e' quello scritto — la stessa logica vorrebbe che i modelli fossero li'
accanto. Si decide quando si sa quanto pesano.

## La misura, che viene prima del codice

La scheda chiede che «i falsi positivi restino sotto una soglia accettabile in
uso reale», e la frase spaventa piu' del dovuto: sembra chiedere un microfono
acceso per giorni prima di poter fare qualsiasi cosa.

Non e' cosi', e il modo giusto e' quello che usano gli autori di
openWakeWord: i falsi positivi si contano su **audio registrato**. Il loro
numero di riferimento e' **meno di 0,5 attivazioni false all'ora**, misurato
su un corpus di circa cinque ore e mezza di voce lontana, musica di sottofondo
e rumore.

Una misura su registrazione si **ripete**. Una misura dal vivo no — e fra sei
mesi, per ritoccare una soglia, si rifarebbe tutto da capo.

L'ordine:

1. **Una sera registrata, una volta sola.** Due o tre ore nella stanza dove
   vivra', con la televisione accesa e la gente che parla. Chi vive in casa
   deve saperlo: e' una registrazione deliberata per tarare, in una cartella
   che poi si cancella. La funzione finita non salva niente, ed e' un altro
   criterio della scheda.
2. **Il conteggio, a tavolino.** La registrazione passa nel modello a soglie
   diverse: ne esce una tabella soglia -> falsi positivi all'ora.
3. **I veri positivi, che sono l'altra meta'.** Trenta o quaranta
   pronunce, da vicino e dall'altra stanza, a voce normale e a voce bassa,
   con la televisione accesa. Da sola, la curva dei falsi positivi porterebbe
   a una soglia altissima e a non farsi sentire mai.
4. **La conferma dal vivo, solo alla fine.** Con la soglia gia' scelta, il
   dispositivo resta acceso qualche giorno registrando **solo** orario e
   punteggio, nessun audio. Se il numero vero assomiglia a quello previsto, il
   criterio e' soddisfatto con una misura invece che con una sensazione.

La misura si fa **nel browser**, non con uno script sul computer: il suono che
conta e' quello che esce dal microfono di quel tablet, con il suo guadagno
automatico e il suo ricampionamento. Misurare altrove misurerebbe un'altra
cosa.

## La parola, che conta piu' della soglia

«Kyra» e' corta, e le parole corte sono la prima causa di falsi positivi. Non
e' un caso che i modelli gia' addestrati di openWakeWord siano quasi tutti di
due parole — *hey jarvis*, *hey mycroft*, *hey rhasspy*.

Quindi il primo giro si fa con un modello **gia' addestrato**: da' una linea
di base e separa due domande che altrimenti si confondono. Se il modello
pronto fa 0,2 falsi all'ora e «Kyra» ne fa otto, il problema e' la parola e
non la taratura — e «ehi Kyra» potrebbe risolverlo da sola.

## Alternative considerate

**openWakeWord in Python, microfono USB sul server.** E' la strada con meno
codice: la libreria e' pensata per questo, e un solo core di un Raspberry Pi 3
regge quindici modelli in tempo reale. Ma sposta l'audio continuo di una
stanza dentro un processo che sta altrove, e indebolisce il criterio sulla
privacy da «non lascia il dispositivo» a «non lascia la casa». Per un progetto
che esiste per tenere in casa cio' che si puo' tenere in casa, e' il verso
sbagliato.

**Una scheda arm64 per stanza.** Stessa struttura della precedente, con piu'
cose da tenere accese e aggiornate. Ha senso il giorno che un punto di ascolto
debba stare dove un tablet non puo' stare.

**Lasciare che sia Alexa a svegliare Shinra.** Funziona gia' e non costa
niente. Ma l'audio va ad Amazon per costruzione, ed e' scritto nel README fra
le cose che Shinra **non** tiene in casa. Usarlo come unica strada vorrebbe
dire rinunciare alla ragione per cui la #30 esiste.

**Aspettare l'hardware giusto.** E' cio' che si e' fatto finora, ed e' costato
una versione. La misura si puo' cominciare con quello che c'e'.
