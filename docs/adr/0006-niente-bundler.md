# 0006 — Niente bundler: moduli ES serviti come sono

- **Stato:** Accettato
- **Data:** 2026-09-24
- **Attuazione:** milestone `v0.5.0`, issue #34

## Contesto

La scheda della #34 chiede di «valutare un bundler leggero (Vite) mantenendo
la possibilita' di servire senza build». La valutazione va fatta adesso e non
dopo, perche' decide la forma del lavoro che resta: con un bundler i moduli si
scrivono in un modo, senza in un altro, e scoprirlo a meta' significa rifarlo.

Lo stato di oggi: ventidue copioni classici, 6.386 righe in tutto, caricati in
ordine da `index.html` con la versione attaccata all'indirizzo. Non sono
moduli: ogni file dichiara i suoi nomi nello spazio globale e legge quelli
degli altri.

Il modo in cui Shinra si aggiorna in casa e' il fatto che pesa di piu'.
`scripts/deploy.sh` fa: fermare il servizio, prendere un tag, reinstallare le
dipendenze Python se sono cambiate, migrare il database, riavviare,
verificare che risponda, e tornare indietro da solo se non risponde. Sul
server Debian non c'e' node, non c'e' npm, e non c'e' nessun passo di
costruzione.

## Decisione

**Nessun bundler.** Quando i copioni diventeranno moduli ES, saranno moduli
nativi serviti dal server cosi' come stanno sul disco, con
`<script type="module">` e `import` fra un file e l'altro.

Le tre cose che un bundler avrebbe dato, e perche' qui non servono:

- **Impacchettare.** Il costo e' una richiesta HTTP per modulo. Ventidue file
  su una rete di casa, dietro HTTP/2, non si misurano: e sono gia' ventidue
  richieste oggi.
- **Minificare.** Tutto il JavaScript sta in **68 KB compressi**. Un
  aggiornamento di Home Assistant ne muove piu' di cosi'.
- **Trasformare.** Non c'e' niente da trasformare: nessun TypeScript, nessun
  JSX, nessuna sintassi che un browser del 2026 non capisca da solo.

E una cosa che un bundler avrebbe **tolto**: il codice servito e' lo stesso che
sta nel repository. Chi apre gli strumenti del browser su una dashboard che si
comporta male legge il file vero, con i commenti che spiegano perche' quella
riga esiste. Su un progetto che una persona sola manutiene in casa propria,
questo vale piu' di qualche kilobyte.

## Il vero ostacolo, che non e' il bundler

I moduli ES non mettono niente nello spazio globale. La pagina invece chiama
le funzioni da li':

- **77** attributi in linea nel markup (59 `onclick`, 9 `onchange`, 6
  `oninput`, 3 `onsubmit`);
- **72** `onclick=` scritti dentro le stringhe che il JavaScript genera, su
  sedici file.

Centoquarantanove punti. Finche' ci sono, `type="module"` non si puo'
aggiungere: spegnerebbe meta' dashboard senza un errore che lo dica — i clic
semplicemente non farebbero niente.

Quindi il lavoro della #34 non e' «aggiungere `type="module"`». E':

1. un **registro dei gesti**: ogni area dichiara le funzioni che il markup
   puo' chiamare, per nome;
2. la **delega degli eventi** su una radice sola, che legge un attributo
   `data-` invece di eseguire una stringa;
3. area per area, gli attributi in linea diventano `data-`;
4. **solo alla fine**, e tutti insieme, i copioni diventano moduli.

I primi tre passi non rompono niente e si fanno uno per volta, con i gesti
dell'editor in CI a guardare. Il quarto e' un interruttore, e si tira quando
non e' rimasto nessun attributo in linea — che e' una cosa che una guardia sa
contare.

## Alternative considerate

**Vite.** E' lo strumento che la scheda nominava. Dev server istantaneo,
costruzione ottimizzata, ecosistema enorme. Ma porta un passo di costruzione:
o node sul server Debian, o gli artefatti costruiti dentro il repository, o la
CI che pubblica un pacchetto che `deploy.sh` deve scaricare. Tutte e tre
peggiorano la cosa che questa versione vuole migliorare — che qualcuno che non
sia l'autore riesca a installarlo.

**esbuild, un solo file costruito e versionato.** Nessun node sul server,
perche' il file costruito sta nel repository. Ma allora due sorgenti dicono la
stessa cosa, e prima o poi divergono: qualcuno modifica un modulo, dimentica
di ricostruire, e la dashboard gira su codice vecchio senza che niente lo
dica. E' la stessa famiglia di guasto della cache, che e' gia' costata un
pomeriggio.

**Una import map, senza toccare gli `onclick`.** Risolverebbe i nomi dei
moduli ma non il problema: gli attributi in linea continuerebbero a cercare
nello spazio globale, che i moduli non riempiono.

**Lasciare i copioni classici per sempre.** E' l'opzione che si sceglie da
sola se non si decide niente, e va detta: funziona. Il prezzo e' che l'ambito
di ogni nome resta l'intera pagina, che e' esattamente cio' che la #34 e' nata
per togliere — «ogni modifica al frontend e' rischiosa perche' l'ambito di una
variabile e' l'intero file».

## Conseguenze

**Positive.** L'aggiornamento in casa resta `deploy.sh` e basta: niente node
sul server, niente artefatti, nessun passo che possa fallire in un modo nuovo.
Il codice servito e' quello scritto. E il lavoro che resta e' incrementale,
non un salto.

**Negative.** Niente tree shaking: un modulo importato per una funzione si
porta dietro tutto. Con 68 KB non e' un problema oggi, e il giorno che lo
diventasse questo ADR si sostituisce — e' a questo che serve la numerazione.
L'ordine di caricamento smette di essere una lista nella pagina e diventa un
grafo di `import`: piu' corretto, ma non si legge piu' tutto da un posto solo.

**Da definire.** Se i moduli debbano restare uno per area, come i copioni di
oggi, o se qualcuno vada spezzato ancora: si vedra' quando avranno importazioni
vere, perche' e' li' che si capisce chi dipende da chi.
