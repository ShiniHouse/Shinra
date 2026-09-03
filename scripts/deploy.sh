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
#   sudo /opt/Shinra/scripts/deploy.sh --rollback      # torna indietro
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
PROTEGGI=0
RIFERIMENTO=""

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

# ---------------------------------------------------------------- argomenti
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)  DRY_RUN=1 ;;
        --rollback) ROLLBACK=1 ;;
        --proteggi-stato|--proteggi-dati) PROTEGGI=1 ;;
        -h|--help)  sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*)         rosso "Opzione sconosciuta: $1"; exit 2 ;;
        *)          RIFERIMENTO="$1" ;;
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
trap 'rm -rf "$RIPARO"' EXIT
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
esegui git_utente fetch --quiet --tags --prune origin

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
    exit 0
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
if [[ $DRY_RUN -eq 0 ]]; then
    tar -czf "$ARCHIVIO" -C "$APP_DIR" \
        --ignore-failed-read config data .env 2>/dev/null || true
    chmod 600 "$ARCHIVIO"
    info "Salvato in $ARCHIVIO ($(du -h "$ARCHIVIO" | cut -f1))"
    # Conserva solo gli ultimi N backup.
    ls -1t "$BACKUP_DIR"/shinra-*.tar.gz 2>/dev/null \
        | tail -n "+$((BACKUP_DA_TENERE + 1))" | xargs -r rm -f
else
    info "[simulazione] tar -czf $ARCHIVIO config data .env"
fi

echo "$ATTUALE" > "${STATO_PRECEDENTE}.tmp" && mv "${STATO_PRECEDENTE}.tmp" "$STATO_PRECEDENTE"

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
