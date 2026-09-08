#!/usr/bin/env bash
#
# Aggiornamento di Shinra su un server Debian.
#
# Sostituisce:  cd /opt/Shinra && git pull && systemctl restart shinra
#
# Cosa fa in piu':
#   - rifiuta di partire se ci sono modifiche locali non salvate
#   - fa un backup di configurazione e dati prima di toccare qualcosa
#   - distribuisce una versione taggata, non l'ultimo commit qualunque
#   - reinstalla le dipendenze solo se sono cambiate
#   - esegue le migrazioni del database quando ci saranno (v0.2.0)
#   - verifica che il servizio risponda davvero dopo il riavvio
#   - torna alla versione precedente da solo se non risponde
#
# Uso:
#   sudo /opt/Shinra/scripts/deploy.sh                 # ultimo tag di release
#   sudo /opt/Shinra/scripts/deploy.sh v0.1.0          # una versione precisa
#   sudo /opt/Shinra/scripts/deploy.sh main            # ultimo commit di main
#   sudo /opt/Shinra/scripts/deploy.sh --rollback      # annulla l'ultimo aggiornamento
#   sudo /opt/Shinra/scripts/deploy.sh --indietro v0.1.0  # installa apposta una
#          versione precedente. Senza questo, lo script si rifiuta di tornare
#          indietro nel tempo: e' successo di riportare il server alla v0.1.0
#          con un comando lanciato per aggiornarlo.
#   sudo /opt/Shinra/scripts/deploy.sh --proteggi-stato  # una volta sola,
#          mette al riparo config/ e data/ da qualunque aggiornamento futuro
#   sudo /opt/Shinra/scripts/deploy.sh --dry-run v0.2.0

set -Eeuo pipefail

APP_DIR="${SHINRA_DIR:-/opt/Shinra}"
SERVICE="${SHINRA_SERVICE:-shinra}"
VENV="$APP_DIR/.venv"
BACKUP_DIR="${SHINRA_BACKUP_DIR:-/var/backups/shinra}"
STATO_PRECEDENTE="$APP_DIR/.deploy-precedente"
BACKUP_DA_TENERE=10
TENTATIVI_HEALTH=15

DRY_RUN=0
ROLLBACK=0
# Consente esplicitamente di installare una versione precedente. Serve a
# distinguere «voglio tornare alla v0.1.0» da «aggiorna», che senza questo
# erano lo stesso comando.
INDIETRO=0
PROTEGGI=0
RIFERIMENTO=""
# Cio' che l'utente ha chiesto per nome, distinto da cio' che lo script ha
# scelto per lui: se la scelta e' nostra e porta indietro, il messaggio deve
# spiegare *perche'* invece di dare la colpa a chi ha premuto invio.
RIFERIMENTO_ESPLICITO=""

rosso()  { printf '\033[0;31m%s\033[0m\n' "$*" >&2; }
verde()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
giallo() { printf '\033[0;33m%s\033[0m\n' "$*"; }
info()   { printf '  %s\n' "$*"; }
passo()  { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }

trap 'rosso "Interrotto alla riga $LINENO. Il servizio potrebbe essere in uno stato intermedio: controlla con  systemctl status $SERVICE"' ERR

esegui() {
    if [[ $DRY_RUN -eq 1 ]]; then
        printf '  [simulazione] %s\n' "$*"
    else
        "$@"
    fi
}

# Tiene i piu' recenti N file che corrispondono al modello e cancella gli
# altri. Sembra una riga sola e infatti lo era, ma `ls` esce con errore
# quando il modello non trova niente, e con `pipefail` quell'errore fermava
# l'aggiornamento — al primo avvio, quando l'istantanea del database non
# esiste ancora. Cioe' esattamente la volta in cui serve che funzioni.
conserva_ultimi() {
    local modello="$1" quanti="$2" vecchi
    vecchi="$(ls -1t $modello 2>/dev/null | tail -n "+$((quanti + 1))" || true)"
    [[ -n "$vecchi" ]] && printf '%s\n' "$vecchi" | xargs -r rm -f
    return 0
}

# ------------------------------------------------- si copia da parte e riparte
#
# Bash non legge tutto lo script in memoria: lo legge a pezzi, mentre lo
# esegue, tenendo il segno con una posizione nel file. Al passo 4 questo
# script aggiorna il codice — **compreso se stesso** — e da quel momento la
# posizione tenuta da bash indica righe di un file diverso. L'esecuzione
# prosegue su testo che non c'entra piu' niente, e lo fa in mezzo a un
# aggiornamento, che e' il momento peggiore possibile.
#
# Non e' teoria: fra la v0.1.0 e la v0.2.0 questo file e' cresciuto di
# ottanta righe. Si lavora su una copia in /tmp, che nessun aggiornamento
# puo' toccare.
if [[ -z "${SHINRA_DEPLOY_COPIA:-}" ]]; then
    COPIA_DI_LAVORO="$(mktemp /tmp/shinra-deploy.XXXXXXXX.sh)"
    cp "$(readlink -f "$0")" "$COPIA_DI_LAVORO"
    chmod +x "$COPIA_DI_LAVORO"
    export SHINRA_DEPLOY_COPIA="$COPIA_DI_LAVORO"
    exec "$COPIA_DI_LAVORO" "$@"
fi

# Da qui in poi si sta eseguendo la copia: si cancella da sola alla fine,
# comunque vada.
trap 'rm -f "${SHINRA_DEPLOY_COPIA:-}"' EXIT

# ---------------------------------------------------------------- argomenti
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)  DRY_RUN=1 ;;
        --rollback) ROLLBACK=1 ;;
        --indietro) INDIETRO=1 ;;
        --proteggi-stato|--proteggi-dati) PROTEGGI=1 ;;
        -h|--help)  sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*)         rosso "Opzione sconosciuta: $1"; exit 2 ;;
        *)          RIFERIMENTO="$1"; RIFERIMENTO_ESPLICITO="$1" ;;
    esac
    shift
done

# ------------------------------------------------------------ preliminari
[[ $EUID -eq 0 ]] || { rosso "Serve root: usa sudo."; exit 1; }
[[ -d "$APP_DIR/.git" ]] || { rosso "$APP_DIR non e' un repository git."; exit 1; }
[[ -x "$VENV/bin/python" ]] || { rosso "Ambiente virtuale assente in $VENV."; exit 1; }

cd "$APP_DIR"
PROPRIETARIO="$(stat -c '%U' "$APP_DIR")"
RIPARO="$(mktemp -d)"
# Un secondo `trap ... EXIT` *sostituisce* il primo, non si aggiunge: qui si
# ripulisce anche la copia dello script, altrimenti resterebbe in /tmp a ogni
# aggiornamento. (Sbagliato una volta, in questa stessa correzione.)
trap 'rm -rf "$RIPARO"; rm -f "${SHINRA_DEPLOY_COPIA:-}"' EXIT
git_utente() { sudo -u "$PROPRIETARIO" git "$@"; }

# La porta la leggiamo dalla configurazione, con ricaduta su 8000.
PORTA="$(sed -n 's/^[[:space:]]*port:[[:space:]]*\([0-9]\+\).*/\1/p' config/config.yaml 2>/dev/null | head -1)"
PORTA="${PORTA:-8000}"

# --------------------------------------------------------------- rollback
if [[ $ROLLBACK -eq 1 ]]; then
    [[ -f "$STATO_PRECEDENTE" ]] || { rosso "Nessuna versione precedente registrata."; exit 1; }
    PRECEDENTE="$(cat "$STATO_PRECEDENTE")"
    passo "Ritorno alla versione $PRECEDENTE"
    metti_da_parte_stato no
    esegui git_utente checkout --quiet --force "$PRECEDENTE"
    ripristina_stato
    esegui "$VENV/bin/pip" install -q -e "$APP_DIR"
    esegui systemctl restart "$SERVICE"
    verde "Ripristinato $PRECEDENTE, con lo stato locale intatto."
    exit 0
fi

# ---------------------------------------- protezione dello stato locale
# I file sotto data/ e config/ sono lo stato reale di QUESTA casa: alias dei
# dispositivi, conoscenza, utenti, token. Sono ancora tracciati da git fino
# alla issue #07, quindi ogni aggiornamento rischia di sovrascriverli.
# skip-worktree dice a git di ignorare la copia locale di quei file.
FILE_DI_STATO=(
    config/config.yaml
    data/users.json
    data/knowledge.json
    data/device_aliases.json
    data/modes.json
    data/sources.json
    data/timers.json
    data/reminders.json
)

# Mette al riparo i file di stato prima di un checkout che potrebbe
# sovrascriverli o cancellarli, e li rimette dopo. Usate sia
# dall'aggiornamento sia da entrambi i percorsi di ritorno indietro:
# un ripristino che perde i dati della casa non e' un ripristino.
STATO_MESSO_DA_PARTE=()

metti_da_parte_stato() {
    local solo_se_rimossi="${1:-no}" da a f nel_vecchio nel_nuovo
    da="${2:-}"; a="${3:-}"
    STATO_MESSO_DA_PARTE=()
    for f in "${FILE_DI_STATO[@]}"; do
        [[ -e "$APP_DIR/$f" ]] || continue
        if [[ "$solo_se_rimossi" == "si" ]]; then
            nel_vecchio=0; nel_nuovo=0
            git_utente cat-file -e "$da:$f" 2>/dev/null && nel_vecchio=1 || true
            git_utente cat-file -e "$a:$f"  2>/dev/null && nel_nuovo=1   || true
            [[ $nel_vecchio -eq 1 && $nel_nuovo -eq 0 ]] || continue
        fi
        mkdir -p "$RIPARO/$(dirname "$f")"
        cp -p "$APP_DIR/$f" "$RIPARO/$f"
        git_utente update-index --no-skip-worktree "$f" 2>/dev/null || true
        git_utente checkout --quiet -- "$f" 2>/dev/null || true
        STATO_MESSO_DA_PARTE+=("$f")
    done
}

ripristina_stato() {
    local f
    for f in "${STATO_MESSO_DA_PARTE[@]:-}"; do
        [[ -n "$f" && -e "$RIPARO/$f" ]] || continue
        mkdir -p "$APP_DIR/$(dirname "$f")"
        cp -p "$RIPARO/$f" "$APP_DIR/$f"
        chown "$PROPRIETARIO" "$APP_DIR/$f" 2>/dev/null || true
        info "ripristinato  $f"
    done
}

proteggi_stato() {
    passo "Protezione dello stato locale"
    local marca archivio protetti=0
    marca="$(date +%Y%m%d-%H%M%S)"
    archivio="$BACKUP_DIR/stato-prima-della-protezione-$marca.tar.gz"

    mkdir -p "$BACKUP_DIR"
    tar -czf "$archivio" -C "$APP_DIR" --ignore-failed-read config data .env 2>/dev/null || true
    chmod 600 "$archivio"
    info "Backup completo in $archivio"

    for f in "${FILE_DI_STATO[@]}"; do
        git_utente ls-files --error-unmatch "$f" >/dev/null 2>&1 || continue
        # Toglie dallo stage senza toccare il file sul disco.
        git_utente reset --quiet -- "$f" 2>/dev/null || true
        git_utente update-index --skip-worktree "$f" 2>/dev/null && {
            info "protetto  $f"
            protetti=$((protetti + 1))
        }
    done

    echo
    if [[ -z "$(git_utente status --porcelain --untracked-files=no)" ]]; then
        verde "$protetti file protetti. Lo stato locale ora e' invisibile a git."
        info "Gli aggiornamenti non potranno piu' sovrascriverli."
    else
        giallo "$protetti file protetti, ma restano modifiche:"
        git_utente status --short --untracked-files=no
    fi
}

if [[ $PROTEGGI -eq 1 ]]; then
    proteggi_stato
    exit 0
fi

# ------------------------------------------------- 1. modifiche locali
passo "Controllo dello stato locale"
SPORCHI="$(git_utente status --porcelain --untracked-files=no || true)"
if [[ -n "$SPORCHI" ]]; then
    # Distingue lo stato della casa dalle modifiche al codice: sono due
    # problemi diversi e la soluzione sbagliata sul primo distrugge dati.
    STATO="$(printf '%s\n' "$SPORCHI"  | awk '{print $NF}' | grep -E '^(data|config)/' || true)"
    CODICE="$(printf '%s\n' "$SPORCHI" | awk '{print $NF}' | grep -vE '^(data|config)/' || true)"

    rosso "Il deploy si ferma: ci sono modifiche locali."
    echo >&2

    if [[ -n "$STATO" ]]; then
        giallo "Stato di questa casa — NON cancellarlo:" >&2
        printf '%s\n' "$STATO" | sed 's/^/    /' >&2
        echo >&2
        info "Sono i tuoi alias, la conoscenza della casa, gli utenti, il token." >&2
        info "Differiscono dal repository perche' contengono i dati reali, ed e'" >&2
        info "giusto cosi'. Sono ancora tracciati da git solo fino alla issue #07." >&2
        echo >&2
        giallo "  sudo $0 --proteggi-stato" >&2
        info "  Fa un backup e dice a git di ignorare questi file. Da eseguire una volta." >&2
        echo >&2
        rosso "  NON usare  git checkout -- .  su questi file:" >&2
        rosso "  sostituirebbe i dati della tua casa con quelli dimostrativi del repository." >&2
        echo >&2
    fi

    if [[ -n "$CODICE" ]]; then
        giallo "Modifiche al codice:" >&2
        printf '%s\n' "$CODICE" | sed 's/^/    /' >&2
        echo >&2
        info "Se non ti servono:   git checkout -- <file>" >&2
        info "Se ti servono:       git stash" >&2
    fi
    exit 1
fi
info "Nessuna modifica locale."

# --------------------------------------------------------- 2. quale versione
passo "Recupero degli aggiornamenti"
# Questo `fetch` non passa da `esegui`, e non e' una dimenticanza: non tocca
# la copia di lavoro ne' il ramo, aggiorna solo i riferimenti remoti.
# Simularlo rendeva `--dry-run` inutile esattamente quando serve — senza i
# riferimenti nuovi lo script confrontava HEAD con se stesso e annunciava
# «gia' aggiornato» mentre c'erano tre versioni da installare. Una prova che
# risponde sempre «niente da fare» non e' una prova.
git_utente fetch --quiet --tags --prune origin

if [[ -z "$RIFERIMENTO" ]]; then
    RIFERIMENTO="$(git_utente tag --list 'v*' --sort=-version:refname | head -1)"
    if [[ -z "$RIFERIMENTO" ]]; then
        giallo "Nessun tag di release trovato: uso origin/main."
        RIFERIMENTO="origin/main"
    else
        info "Ultima release disponibile: $RIFERIMENTO"
    fi
fi

# Se e' un nome di branch, prendiamo la versione remota.
if git_utente show-ref --quiet "refs/remotes/origin/$RIFERIMENTO"; then
    RIFERIMENTO="origin/$RIFERIMENTO"
fi

git_utente rev-parse --verify --quiet "$RIFERIMENTO^{commit}" >/dev/null \
    || { rosso "Riferimento sconosciuto: $RIFERIMENTO"; exit 1; }

ATTUALE="$(git_utente rev-parse HEAD)"
NUOVO="$(git_utente rev-parse "$RIFERIMENTO^{commit}")"

if [[ "$ATTUALE" == "$NUOVO" ]]; then
    verde "Gia' aggiornato a $(git_utente log --oneline -1 HEAD)."
    # Senza argomenti si distribuisce l'ultimo *tag*, non l'ultimo commit: e'
    # voluto, perche' un server di casa non deve seguire il ramo di sviluppo.
    # Ma se main e' avanti e nessuno lo dice, sembra che l'aggiornamento non
    # funzioni — ed e' successo davvero.
    AVANTI="$(git_utente rev-list --count "HEAD..origin/main" 2>/dev/null || echo 0)"
    if [[ "$AVANTI" -gt 0 ]]; then
        echo
        giallo "Su origin/main ci sono $AVANTI commit piu' recenti, senza un tag di release."
        info "Per installarli comunque:   sudo $0 main"
        info "Oppure attendi il prossimo tag: e' cio' che questo script installa da solo."
    fi
    exit 0
fi

# Un aggiornamento che riporta indietro nel tempo non e' un aggiornamento.
#
# Senza argomenti lo script installa l'ultimo *tag*, ed e' voluto: un server
# di casa non deve seguire il ramo di sviluppo. Ma se il tag piu' recente e'
# piu' vecchio di cio' che gira — perche' si sta lavorando su `main` e il tag
# della versione in corso non e' ancora stato creato — la stessa regola
# diventa una macchina del tempo, e la casa torna a una versione di settimane
# prima senza che nessuno l'abbia chiesto. E' successo davvero: il server e'
# stato riportato alla v0.1.0 da un comando lanciato per aggiornarlo.
#
# Il codice torna indietro, i dati no: le migrazioni non si annullano, e il
# database resta con lo schema nuovo sotto un'applicazione che si aspetta
# quello vecchio.
if git_utente merge-base --is-ancestor "$NUOVO" "$ATTUALE" 2>/dev/null; then
    echo
    rosso "Questo non e' un aggiornamento: e' un ritorno a una versione precedente."
    info "In esecuzione: $(git_utente log --oneline -1 "$ATTUALE")"
    info "Richiesta:     $(git_utente log --oneline -1 "$NUOVO")"
    echo
    if [[ -z "$RIFERIMENTO_ESPLICITO" ]]; then
        giallo "Nessuna versione indicata, quindi ho scelto l'ultimo tag: $RIFERIMENTO."
        info "Il tag della versione in esecuzione non esiste ancora."
        info "Per prendere l'ultimo codice:      sudo $0 main"
    fi
    info "Per tornare indietro davvero:      sudo $0 --indietro $RIFERIMENTO"
    info "Per annullare l'ultimo aggiornamento: sudo $0 --rollback"
    if [[ $INDIETRO -eq 0 ]]; then
        exit 1
    fi
    giallo "Procedo all'indietro come richiesto."
fi

info "Da:  $(git_utente log --oneline -1 "$ATTUALE")"
info "A:   $(git_utente log --oneline -1 "$NUOVO")"
echo
git_utente log --oneline "$ATTUALE..$NUOVO" 2>/dev/null | sed 's/^/    /' | head -25

# --------------------------------------------------------------- 3. backup
passo "Backup di configurazione e dati"
MARCA="$(date +%Y%m%d-%H%M%S)"
ARCHIVIO="$BACKUP_DIR/shinra-$MARCA.tar.gz"
esegui mkdir -p "$BACKUP_DIR"

# Il database e' vivo mentre facciamo il backup: il servizio non e' ancora
# fermo. Copiarlo con tar mentre una transazione e' a meta' produce un file
# che sembra a posto e non lo e' — e un backup che non si puo' ripristinare
# e' peggio di nessun backup, perche' ci si conta sopra. L'API di backup di
# SQLite fa una copia coerente di un database in uso: questa e' quella
# buona, il tar la porta con se' insieme al resto.
ISTANTANEA="$BACKUP_DIR/shinra-db-$MARCA.db"
if [[ -f "$APP_DIR/data/shinra.db" ]]; then
    if [[ $DRY_RUN -eq 0 ]]; then
        if "$VENV/bin/python" - "$APP_DIR/data/shinra.db" "$ISTANTANEA" <<'PY'
import sqlite3, sys
sorgente, destinazione = sys.argv[1], sys.argv[2]
with sqlite3.connect(sorgente) as origine, sqlite3.connect(destinazione) as copia:
    origine.backup(copia)
PY
        then
            chmod 600 "$ISTANTANEA"
            info "Istantanea coerente del database: $ISTANTANEA"
        else
            rosso "Non sono riuscito a copiare il database in modo coerente."
            rosso "Mi fermo: aggiornare senza un backup valido non e' accettabile."
            exit 1
        fi
    else
        info "[simulazione] istantanea SQLite in $ISTANTANEA"
    fi
fi

if [[ $DRY_RUN -eq 0 ]]; then
    tar -czf "$ARCHIVIO" -C "$APP_DIR" \
        --ignore-failed-read config data .env 2>/dev/null || true
    chmod 600 "$ARCHIVIO"
    info "Salvato in $ARCHIVIO ($(du -h "$ARCHIVIO" | cut -f1))"
    # Conserva solo gli ultimi N backup.
    conserva_ultimi "$BACKUP_DIR/shinra-*.tar.gz" "$BACKUP_DA_TENERE"
    conserva_ultimi "$BACKUP_DIR/shinra-db-*.db" "$BACKUP_DA_TENERE"
else
    info "[simulazione] tar -czf $ARCHIVIO config data .env"
fi

if [[ $DRY_RUN -eq 0 ]]; then
    echo "$ATTUALE" > "${STATO_PRECEDENTE}.tmp" && mv "${STATO_PRECEDENTE}.tmp" "$STATO_PRECEDENTE"
fi

# ------------------------------------------- 3b. migrazione dello stato
# Quando un aggiornamento smette di tracciare un file di stato — e' cio' che
# fa la issue #07 con config.yaml e i dati personali — git lo considera
# rimosso dal progetto e lo cancella dalla cartella di lavoro. Qui li
# mettiamo da parte prima del checkout e li rimettiamo subito dopo, cosi'
# la transizione avviene senza che il server perda nulla.
passo "Migrazione dello stato locale"
if [[ $DRY_RUN -eq 1 ]]; then
    for f in "${FILE_DI_STATO[@]}"; do
        [[ -e "$APP_DIR/$f" ]] || continue
        if git_utente cat-file -e "$ATTUALE:$f" 2>/dev/null \
           && ! git_utente cat-file -e "$NUOVO:$f" 2>/dev/null; then
            info "[simulazione] metterei da parte e ripristinerei  $f"
        fi
    done
else
    metti_da_parte_stato si "$ATTUALE" "$NUOVO"
    if [[ ${#STATO_MESSO_DA_PARTE[@]} -eq 0 ]]; then
        info "Nessun file di stato viene rimosso da questo aggiornamento."
    else
        for f in "${STATO_MESSO_DA_PARTE[@]}"; do info "messo da parte  $f"; done
        info "${#STATO_MESSO_DA_PARTE[@]} file saranno ripristinati dopo l'aggiornamento."
    fi
fi

# ------------------------------------------------------ 4. aggiornamento
passo "Aggiornamento del codice"
esegui git_utente checkout --quiet --force --detach "$NUOVO"
info "Ora su $(git_utente log --oneline -1 HEAD 2>/dev/null || echo "$NUOVO")"

if [[ $DRY_RUN -eq 0 && ${#STATO_MESSO_DA_PARTE[@]} -gt 0 ]]; then
    ripristina_stato
    verde "Stato locale conservato: ${#STATO_MESSO_DA_PARTE[@]} file."
fi

# ---------------------------------------------- 4b. cartelle abbandonate
# Lo spostamento sotto src/ (issue #16) lascia indietro core/, server/ e
# integrations/: git non le rimuove perche' dentro c'e' ancora __pycache__,
# che non e' tracciato. Restano a confondere chi guarda la cartella, e un
# .pyc di un modulo che non esiste piu' e' il genere di cosa che un giorno
# spiega un errore assurdo. Si cancellano solo se git non ci tiene piu'
# niente: la condizione e' la garanzia che non si stia buttando via codice.
for vecchia in core server integrations; do
    if [[ -d "$APP_DIR/$vecchia" && -z "$(git_utente ls-files "$vecchia")" ]]; then
        info "Rimuovo la cartella abbandonata $vecchia/."
        esegui rm -rf "${APP_DIR:?}/$vecchia"
    fi
done

# ------------------------------------------------------- 5. dipendenze
passo "Dipendenze"
if git_utente diff --quiet "$ATTUALE" "$NUOVO" -- pyproject.toml requirements.txt; then
    info "Invariate, nessuna installazione."
else
    info "Cambiate: reinstallo."
    if [[ -f pyproject.toml ]]; then
        esegui "$VENV/bin/pip" install -q --upgrade -e "$APP_DIR"
    else
        esegui "$VENV/bin/pip" install -q --upgrade -r requirements.txt
    fi
fi

# ------------------------------------------------------- 6. migrazioni
passo "Migrazioni del database"
if [[ -f "$APP_DIR/alembic.ini" ]]; then
    esegui "$VENV/bin/alembic" upgrade head
    info "Schema aggiornato."
else
    info "Nessuna migrazione da applicare (previste dalla v0.2.0)."
fi

# --------------------------------------------------------- 7. riavvio
passo "Riavvio del servizio"
esegui systemctl daemon-reload
esegui systemctl restart "$SERVICE"

if [[ $DRY_RUN -eq 1 ]]; then
    echo
    giallo "Simulazione conclusa: nulla e' stato modificato."
    exit 0
fi

# ------------------------------------------------- 8. verifica di salute
passo "Verifica che il servizio risponda"
SANO=0
for tentativo in $(seq 1 "$TENTATIVI_HEALTH"); do
    sleep 2
    # Qualsiasi risposta HTTP va bene, anche 401: significa che il processo
    # e' vivo e sta servendo. Solo l'assenza di risposta e' un guasto.
    CODICE=""
    CODICE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 \
              "http://127.0.0.1:$PORTA/api/status" 2>/dev/null)" || CODICE=""
    # Un curl fallito restituisce 000 o stringa vuota: entrambi sono guasti.
    if [[ -n "$CODICE" && "$CODICE" != "000" ]]; then
        info "Risponde su :$PORTA dopo ${tentativo} tentativi (HTTP $CODICE)."
        SANO=1
        break
    fi
    printf '  attesa... %d/%d\n' "$tentativo" "$TENTATIVI_HEALTH"
done

if [[ $SANO -eq 0 ]]; then
    echo
    rosso "Il servizio non risponde su :$PORTA dopo $((TENTATIVI_HEALTH * 2)) secondi."
    rosso "Ultime righe del log:"
    journalctl -u "$SERVICE" -n 25 --no-pager >&2 || true
    echo
    giallo "Ritorno automatico alla versione precedente ($ATTUALE)..."
    trap - ERR   # da qui in poi gestiamo noi gli errori, uno alla volta
    metti_da_parte_stato no
    git_utente checkout --quiet --force "$ATTUALE" || true
    ripristina_stato
    "$VENV/bin/pip" install -q -e "$APP_DIR" 2>/dev/null || true
    systemctl restart "$SERVICE" || true
    sleep 4
    rosso "Ripristinata la versione precedente. L'aggiornamento NON e' andato a buon fine."
    rosso "Configurazione e dati sono in $ARCHIVIO."
    exit 1
fi

# --------------------------------------------------------------- riepilogo
echo
verde "═══ Aggiornamento completato ═══"
info "Versione:  $(git_utente log --oneline -1 HEAD)"
info "Backup:    $ARCHIVIO"
info "Rollback:  sudo $0 --rollback"
echo
systemctl status "$SERVICE" --no-pager --lines=0 || true
