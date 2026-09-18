# Shinra in un contenitore. Riferimento: issue #37.
#
# Due stadi. Il primo installa le dipendenze — e' il passaggio lento, e
# dipende solo da `pyproject.toml`: finche' quello non cambia, Docker riusa
# la cache anche quando il codice cambia. Il secondo prende l'ambiente gia'
# pronto e ci mette sopra il progetto.
#
# Il risultato non contiene ne' compilatori ne' sorgenti di dipendenze: quello
# che serve a costruire resta nel primo stadio e non viaggia.

# --------------------------------------------------------------- costruzione
FROM python:3.12-slim-bookworm AS costruzione

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# `build-essential` e `libffi-dev` servono solo se per una dipendenza non
# esiste una ruota gia' pronta per questa architettura — succede su arm64 piu'
# spesso che su amd64, ed e' il motivo per cui questo stadio esiste invece di
# installare tutto nell'immagine finale.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /sorgenti

# Prima solo cio' che descrive le dipendenze: cosi' un commit che tocca il
# codice non fa ripartire l'installazione da capo.
COPY pyproject.toml ./
COPY src/shinra/__init__.py src/shinra/__init__.py
RUN pip install --upgrade pip && pip install .

# Poi il progetto vero, e si reinstalla solo il pacchetto — le dipendenze
# sono gia' li'.
COPY . .
RUN pip install --no-deps .

# ------------------------------------------------------------------ servizio
FROM python:3.12-slim-bookworm AS servizio

LABEL org.opencontainers.image.title="Shinra" \
      org.opencontainers.image.description="Hub domotico con IA locale, Home Assistant e voce" \
      org.opencontainers.image.source="https://github.com/ShiniHouse/Shinra" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    # `percorsi.RADICE` decide dove stanno dati, configurazione e `.env`.
    # Dirlo esplicitamente toglie di mezzo la ricerca del file-segnale, che
    # in un contenitore non ha nessun motivo di essere indovinata.
    SHINRA_RADICE=/app

COPY --from=costruzione /opt/venv /opt/venv

WORKDIR /app

# Solo cio' che serve a girare: il pacchetto e' gia' installato nel venv, qui
# ci vanno i file che l'applicazione legge dal disco.
COPY web/ ./web/
COPY migrazioni/ ./migrazioni/
COPY alembic.ini run.py ./
COPY scripts/ ./scripts/

# L'esempio di configurazione sta **fuori** da `/app/config`, perche' quella
# cartella e' un volume: un volume vuoto montato sopra nasconderebbe il file,
# e chi apre il contenitore non troverebbe il riferimento commentato. Ce lo
# mette dentro l'avvio, se manca.
COPY config/config.example.yaml /opt/shinra/config.example.yaml
COPY docker/avvio.sh /usr/local/bin/avvio.sh

# Non si gira da root. I dati stanno in cartelle che appartengono a `shinra`,
# cosi' i volumi con nome ne ereditano il proprietario alla creazione.
RUN useradd --system --create-home --uid 10001 shinra \
    && mkdir -p /app/data /app/config \
    && chown -R shinra:shinra /app \
    && chmod +x /usr/local/bin/avvio.sh

USER shinra

VOLUME ["/app/data", "/app/config"]
EXPOSE 8000

# `/api/auth/status` risponde anche a chi non e' entrato: e' la rotta giusta
# per chiedere «sei viva?» senza credenziali.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/auth/status', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/avvio.sh"]
CMD ["python", "run.py"]
