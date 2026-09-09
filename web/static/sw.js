const CACHE_NAME = 'shinra-v2';
const ASSETS = [
  '/',
  '/static/manifest.json',
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/lucide@latest'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS).catch(() => {});
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Ignora richieste API per avere sempre dati live
  if (event.request.url.includes('/api/')) {
    return;
  }
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// --------------------------------------------------------------- notifiche
//
// Da qui in giu' e' la issue #29. Prima questo file gestiva installazione,
// cache e richieste, e non aveva alcun handler per l'evento `push`: il
// sistema non poteva raggiungere nessuno con l'applicazione chiusa.

// Quanto sono urgenti le cose, e cosa comporta. `requireInteraction` tiene la
// notifica sullo schermo finche' non la si tocca: giusto per un allarme,
// insopportabile per un promemoria della spesa.
const URGENTE = 'urgente';

self.addEventListener('push', (event) => {
  let avviso = {};
  try {
    avviso = event.data ? event.data.json() : {};
  } catch (errore) {
    // Un carico illeggibile non deve far sparire la notifica: qualcosa e'
    // successo, e dirlo genericamente e' meglio che tacere.
    avviso = {};
  }

  const titolo = avviso.titolo || 'Shinra';
  const urgente = avviso.priorita === URGENTE;

  const opzioni = {
    body: avviso.testo || '',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-192.png',
    // Le notifiche della stessa categoria si sostituiscono invece di
    // impilarsi: cinque promemoria diventano cinque righe da chiudere a
    // mano, e chi le chiude a mano poi le disattiva.
    tag: avviso.categoria || 'shinra',
    renotify: urgente,
    requireInteraction: urgente,
    // Una vibrazione piu' insistente per cio' che non puo' aspettare.
    vibrate: urgente ? [200, 100, 200, 100, 200] : [100],
    data: {
      destinazione: avviso.destinazione || '/',
      categoria: avviso.categoria || '',
      priorita: avviso.priorita || ''
    }
  };

  event.waitUntil(self.registration.showNotification(titolo, opzioni));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const destinazione = (event.notification.data && event.notification.data.destinazione) || '/';

  // Se una finestra dell'applicazione e' gia' aperta la si porta in primo
  // piano e la si sposta, invece di aprirne una seconda: due schede della
  // stessa casa che si contendono lo stesso WebSocket sono un problema, non
  // una comodita'.
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((finestre) => {
      for (const finestra of finestre) {
        if (finestra.url.includes(self.registration.scope) && 'focus' in finestra) {
          if ('navigate' in finestra) {
            finestra.navigate(destinazione).catch(() => {});
          }
          return finestra.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(destinazione);
      }
      return undefined;
    })
  );
});

// La chiave del server arriva in base64url e `subscribe()` la vuole in byte.
function chiaveInByte(base64url) {
  const riempimento = '='.repeat((4 - (base64url.length % 4)) % 4);
  const normale = (base64url + riempimento).replace(/-/g, '+').replace(/_/g, '/');
  const grezzo = self.atob(normale);
  const byte = new Uint8Array(grezzo.length);
  for (let i = 0; i < grezzo.length; i += 1) {
    byte[i] = grezzo.charCodeAt(i);
  }
  return byte;
}

// Il servizio push puo' revocare una sottoscrizione e darne una nuova. Senza
// questo handler il telefono smette di ricevere in silenzio, ed e' il modo
// piu' comune in cui le notifiche «smettono di funzionare da sole».
//
// La chiave del server va richiesta di nuovo: `event.oldSubscription` c'e'
// solo su alcuni browser, e la sua `applicationServerKey` e' un ArrayBuffer
// che non tutti espongono. Chiederla e' l'unica strada che funziona ovunque.
self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil(
    fetch('/api/notifiche/chiave', { credentials: 'include' })
      .then((risposta) => risposta.json())
      .then((dati) => {
        if (!dati.chiave) {
          throw new Error('nessuna chiave dal server');
        }
        return self.registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: chiaveInByte(dati.chiave)
        });
      })
      .then((nuova) => {
        const chiavi = nuova.toJSON().keys || {};
        return fetch('/api/notifiche/sottoscrivi', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            endpoint: nuova.endpoint,
            p256dh: chiavi.p256dh,
            auth: chiavi.auth,
            nome: 'Dispositivo'
          })
        });
      })
      .catch(() => {})
  );
});
