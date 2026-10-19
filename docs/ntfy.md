# Notifiche con ntfy, in casa

[ntfy](https://ntfy.sh) è un piccolo server di notifiche. Messo **in casa**, le notifiche di Shinra arrivano al telefono
senza passare da nessun servizio di terzi. È facoltativo e spento di default (decisione sui canali esterni: ADR 0011).

## Con Docker

1. In `.env`, accanto a `docker-compose.yml`:

   ```
   SHINRA_NTFY_URL=http://ntfy:80
   NTFY_BASE_URL=http://192.168.1.20:8090   # l'indirizzo di QUESTA macchina in casa, come lo vede il telefono
   ```

2. ```bash
   docker compose --profile ntfy up -d
   ```

3. Nell'app ntfy (iPhone/Android): **Impostazioni › Server predefinito** = `http://192.168.1.20:8090` (o aggiungi il server
   quando ti iscrivi).
4. In Shinra: **Impostazioni › Notifiche**, spunta **«Su ntfy, in casa»**. Compaiono il server e l'argomento privato:
   iscriviti a quell'argomento nell'app ntfy. «Mandami una prova» per controllare.

## Senza Docker (installazione a mano)

Installa ntfy sul server (pacchetto della tua distribuzione, o il binario da <https://docs.ntfy.sh/install/>), avvialo in
ascolto sulla rete di casa e metti in `config/config.yaml`:

```yaml
notifiche:
  ntfy_url: "http://192.168.1.20:8090"
```

Il resto è uguale.

## Cosa non fa, per scelta

- **Non accetta indirizzi pubblici.** Shinra rifiuta `ntfy.sh` e qualunque server fuori dalla rete di casa: il punto è non
  passare da terzi.
- **Non esporre ntfy su internet.** Su un ntfy senza account l'argomento *è* la chiave: chi lo conosce legge gli avvisi.
  L'argomento di Shinra è un'impronta calcolata col segreto del server, ma non è un motivo per aprire la porta.
- **Solo in uscita.** Shinra manda gli avvisi; non riceve comandi da ntfy.

## iPhone: un limite da conoscere

Le notifiche istantanee su iPhone passano da Apple, e un ntfy autonomo ha bisogno di inoltrare una richiesta *senza
contenuto* a `ntfy.sh` per svegliare l'app (`upstream-base-url`). Shinra **non lo attiva**: dunque su iPhone ntfy autonomo
può arrivare in ritardo o solo quando riapri l'app. Se vuoi quella richiesta di risveglio (non contiene il testo
dell'avviso, ma `ntfy.sh` vede che esiste un messaggio) è una scelta tua, sul server ntfy. Su Android non serve.
