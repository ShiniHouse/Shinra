"""La conoscenza recuperata invece che riversata.

`get_enabled_knowledge_summary()` concatenava **tutti** i fatti abilitati e li
infilava nel prompt a ogni richiesta. Con la modalita' apprendimento
funzionante la conoscenza cresce in fretta, e il contesto cresceva con lei:
prima si paga in latenza, poi si satura la finestra e i fatti piu' vecchi
vengono troncati **in silenzio**. La casa dimentica senza dirlo, che e' il
difetto peggiore possibile per una funzione chiamata «memoria».

Tre cose che questi test difendono:

**Il recupero non deve mai far sapere alla casa meno di prima.** Sotto una
certa quantita' si manda tutto, come si e' sempre fatto: il problema esiste a
duecento fatti, non a venti.

**La ricerca e' ibrida perche' i vettori sbagliano proprio dove fa male.** Un
embedding avvicina «la password del wifi» a «la chiave della rete» — ed e'
cio' che serve — ma appiattisce «4471» e «4417» sullo stesso punto, perche'
semanticamente sono entrambi «un numero».

**Senza embedding la casa risponde peggio, non smette di sapere.** Ollama
spento o modello non installato lasciano la strada testuale.

Nessun test qui chiama Ollama: i vettori sono finti e scelti a mano, cosi' i
punteggi sono verificabili invece che plausibili.

Riferimento: issue #32.
"""

from __future__ import annotations

import pytest

from shinra.domain import recupero as dominio
from shinra.infra.db import depositi
from shinra.services.conoscenza import ServizioConoscenza

FATTI = [
    ("Il codice del wifi di casa e' 4471", "casa"),
    ("La caldaia e' in cantina, dietro la porta verde", "casa"),
    ("Il gatto si chiama Milo e mangia alle 7", "famiglia"),
    ("Il medico di base e' il dottor Rossi, telefono 0512345", "famiglia"),
    ("La chiave di scorta e' dal vicino del secondo piano", "casa"),
]


def fatto(identificativo: str, testo: str, vettore=None) -> dominio.Fatto:
    return dominio.Fatto(identificativo, testo, vettore=vettore)


# ======================================================= i vettori


def test_il_coseno_di_due_vettori_identici_e_uno():
    assert dominio.coseno([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_il_coseno_di_due_ortogonali_e_zero():
    assert dominio.coseno([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_la_direzione_conta_piu_della_lunghezza():
    """Due vettori paralleli di lunghezza diversa dicono la stessa cosa."""
    assert dominio.coseno([1.0, 1.0], [10.0, 10.0]) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "primo,secondo",
    [([], [1.0]), ([1.0], []), ([1.0, 0.0], [1.0, 0.0, 0.0]), ([0.0, 0.0], [1.0, 1.0])],
)
def test_un_vettore_assente_o_malformato_vale_zero(primo, secondo):
    """Un vettore assente non e' un vettore ortogonale: trattarlo come tale
    darebbe un punteggio inventato invece che nessun punteggio."""
    assert dominio.coseno(primo, secondo) == 0.0


# ======================================================= il testo


def test_una_cifra_sbagliata_conta():
    """Un embedding appiattisce «4471» e «4417» sullo stesso punto, perche'
    semanticamente sono entrambi «un numero». Il testo no."""
    giusto = dominio.somiglianza_testuale("il codice 4471", "Il codice del wifi e' 4471")
    sbagliato = dominio.somiglianza_testuale("il codice 4417", "Il codice del wifi e' 4471")

    assert giusto > sbagliato
    assert giusto == pytest.approx(1.0)


def test_un_numero_pesa_piu_di_una_parola():
    """Il raddoppio dei numeri, provato dove cambia **chi vince** e non solo
    di quanto.

    La prima versione di questo test guardava solo che «4471» battesse
    «4417», e un controllo di mutazione ha mostrato che passava lo stesso
    togliendo il raddoppio: quel confronto lo vince anche il conteggio
    semplice. Qui invece i due fatti pareggiano senza il raddoppio, e con il
    raddoppio vince quello che porta il numero — che e' il punto.
    """
    domanda = "codice 4471"

    con_il_numero = dominio.somiglianza_testuale(domanda, "la combinazione e' 4471")
    con_la_parola = dominio.somiglianza_testuale(domanda, "il codice del garage")

    assert con_il_numero > con_la_parola


def test_le_parole_vuote_non_contano():
    """Senza, «qual e' il...» somiglierebbe a tutto."""
    assert dominio.parole("qual e' il codice del wifi") == {"codice", "wifi"}


def test_i_numeri_corti_si_tengono():
    """«La stanza 3» e' esattamente cio' che i vettori non distinguono."""
    assert "3" in dominio.parole("la stanza 3")


def test_gli_accenti_non_contano():
    """Chi parla all'Echo non scrive, e il riconoscimento vocale gli accenti
    li mette come gli pare."""
    assert dominio.parole("perché") == dominio.parole("perche")


def test_un_fatto_lungo_non_e_penalizzato():
    """Si divide per le parole della domanda e non per l'unione: un fatto
    lungo che contiene tutto cio' che si e' chiesto e' una risposta buona, e
    penalizzarlo premierebbe i fatti brevi e generici."""
    breve = dominio.somiglianza_testuale("caldaia", "La caldaia")
    lungo = dominio.somiglianza_testuale(
        "caldaia", "La caldaia e' in cantina dietro la porta verde accanto ai contatori"
    )

    assert lungo == breve == pytest.approx(1.0)


# ======================================================= la soglia


@pytest.mark.parametrize("quanti,atteso", [(0, False), (10, False), (25, False), (26, True), (500, True)])
def test_sotto_la_soglia_non_si_recupera(quanti, atteso):
    """Il problema esiste a duecento fatti, non a venti: un recupero
    imperfetto dove non serviva farebbe perdere risposte che prima
    funzionavano."""
    assert dominio.serve_recuperare(quanti) is atteso


# ======================================================= la ricerca


def test_una_domanda_specifica_recupera_i_fatti_pertinenti():
    """Il secondo criterio di accettazione della scheda."""
    fatti = [fatto(str(i), t) for i, (t, _) in enumerate(FATTI)]

    trovati = dominio.cerca("qual e' il codice del wifi", fatti)

    assert [t.fatto.identificativo for t in trovati] == ["0"]


def test_e_non_gli_altri():
    """Una domanda che non c'entra niente non tira dentro nessun fatto."""
    fatti = [fatto(str(i), t) for i, (t, _) in enumerate(FATTI)]

    assert dominio.cerca("che tempo fa a Milano domani", fatti) == []


def test_la_soglia_scarta_le_somiglianze_deboli():
    """Il caso che il test di sopra **non** copre, e che un controllo di
    mutazione ha scoperto: li' nessun fatto aveva alcuna parola in comune,
    quindi venivano scartati prima ancora di arrivare alla soglia.

    Qui un fatto una parola in comune ce l'ha — «caldaia» su quattro parole,
    cioe' 0,25 — e resta sotto la soglia di 0,28. Senza la soglia entrerebbe
    nel prompt e lo riempirebbe di rumore: un fatto su cinque pertinente e'
    peggio di nessun fatto, perche' il modello ci costruisce sopra.
    """
    fatti = [fatto("0", "La caldaia e' in cantina")]
    domanda = "la caldaia ha una manutenzione annuale programmata"

    assert dominio.somiglianza_testuale(domanda, fatti[0].testo) == pytest.approx(0.25)
    assert dominio.somiglianza_testuale(domanda, fatti[0].testo) < dominio.SOGLIA_PUNTEGGIO
    assert dominio.cerca(domanda, fatti) == []


def test_ma_una_somiglianza_sopra_la_soglia_passa():
    """Il rovescio della soglia: senza, «non passa mai niente» supererebbe
    il test di sopra."""
    fatti = [fatto("0", "La caldaia e' in cantina")]

    assert dominio.cerca("dove sta la caldaia", fatti)


def test_senza_vettori_si_cerca_lo_stesso():
    """Ollama spento o modello non installato: la casa risponde peggio, non
    smette di sapere."""
    fatti = [fatto(str(i), t) for i, (t, _) in enumerate(FATTI)]

    trovati = dominio.cerca("come si chiama il gatto", fatti, vettore_domanda=None)

    assert trovati
    assert trovati[0].solo_testuale


def test_i_vettori_trovano_cio_che_il_testo_non_trova():
    """«Il numero del dottore» non contiene nessuna parola di «telefono
    0512345»: e' il caso per cui gli embedding esistono."""
    fatti = [
        fatto("0", "Il medico di base e' il dottor Rossi, telefono 0512345", vettore=[1.0, 0.0]),
        fatto("1", "Il gatto si chiama Milo", vettore=[0.0, 1.0]),
    ]

    # La domanda non condivide **nessuna** parola con il fatto: e' il caso
    # per cui gli embedding esistono, e la prima versione di questo test
    # sbagliava proprio qui, chiedendo «a chi telefono» — parola che stava
    # anche nel fatto, e che quindi il testo trovava benissimo.
    domanda = "a chi mi rivolgo se sto poco bene"

    solo_testo = dominio.cerca(domanda, fatti, vettore_domanda=None)
    con_vettori = dominio.cerca(domanda, fatti, vettore_domanda=[1.0, 0.0])

    assert solo_testo == []
    assert [t.fatto.identificativo for t in con_vettori] == ["0"]


def test_il_numero_batte_la_somiglianza_semantica():
    """Due fatti semanticamente identici, uno con il numero giusto: e' il
    caso che la ricerca ibrida esiste per risolvere."""
    fatti = [
        fatto("giusto", "Il codice del cancello e' 4471", vettore=[1.0, 0.0]),
        fatto("sbagliato", "Il codice del garage e' 9902", vettore=[1.0, 0.0]),
    ]

    trovati = dominio.cerca("qual e' il codice 4471", fatti, vettore_domanda=[1.0, 0.0])

    assert trovati[0].fatto.identificativo == "giusto"


def test_non_si_superano_mai_i_fatti_massimi():
    """E' il numero che rende costante il contesto."""
    fatti = [fatto(str(i), f"Il fatto numero {i} riguarda la casa") for i in range(200)]

    trovati = dominio.cerca("un fatto sulla casa", fatti, massimo=dominio.MASSIMO_FATTI)

    assert len(trovati) <= dominio.MASSIMO_FATTI


def test_l_ordine_e_dal_piu_pertinente():
    fatti = [
        fatto("poco", "La caldaia e' in cantina", vettore=[0.5, 0.5]),
        fatto("molto", "Il codice del wifi e' 4471", vettore=[1.0, 0.0]),
    ]

    trovati = dominio.cerca("il codice del wifi", fatti, vettore_domanda=[1.0, 0.0])

    assert trovati[0].fatto.identificativo == "molto"


# ======================================================= l'impronta


def test_l_impronta_cambia_con_il_testo():
    """E' cio' che fa lavorare il ricalcolo da solo: un vettore vecchio non
    da' errore, da' risposte sbagliate."""
    assert dominio.impronta("un fatto") == dominio.impronta("un fatto")
    assert dominio.impronta("un fatto") != dominio.impronta("un fatto diverso")


# ======================================================= il servizio


@pytest.fixture
def senza_ollama(monkeypatch):
    """Ollama che non risponde: nessun embedding, solo testo."""
    from shinra.infra.llm import embedding

    async def niente(testi):
        return [None for _ in testi]

    monkeypatch.setattr(embedding, "calcola", niente)


@pytest.fixture
def con_ollama(monkeypatch):
    """Un embedding finto ma deterministico: una dimensione per parola
    chiave, cosi' i punteggi si possono verificare a mano."""
    from shinra.infra.llm import embedding

    CHIAVI = ["wifi", "caldaia", "gatto", "medico", "chiave"]

    async def finto(testi):
        fuori = []
        for testo in testi:
            piatto = dominio.normalizza(testo)
            fuori.append([1.0 if k in piatto else 0.0 for k in CHIAVI] or None)
        return [v if any(v) else None for v in fuori]

    monkeypatch.setattr(embedding, "calcola", finto)
    monkeypatch.setattr(embedding, "modello", lambda: "finto")


@pytest.fixture(autouse=True)
def conoscenza_nota():
    """Il database di prova nasce con la casa di esempio, e questi test
    contano i fatti: si parte da zero e si mette dentro solo cio' che serve.

    L'ha fatto notare la prima esecuzione, in cui dodici test fallivano per
    un fatto di esempio che nessuno aveva scritto.
    """
    for riga in depositi.fatti.elenco():
        depositi.fatti.cancella(str(riga["id"]))
    yield


def riempi(quanti: int) -> None:
    from shinra.infra.data_store import data_store

    for i in range(quanti):
        data_store.add_knowledge_item(f"Il fatto numero {i} riguarda qualcosa di casa", "generale")


async def test_con_pochi_fatti_si_manda_tutto(senza_ollama):
    """Come prima: nessuna chiamata di embedding, nessuna latenza aggiunta,
    nessun rischio di lasciare fuori quello giusto."""
    from shinra.infra.data_store import data_store

    for testo, categoria in FATTI:
        data_store.add_knowledge_item(testo, categoria)

    servizio = ServizioConoscenza()
    prompt = await servizio.per_la_domanda("qual e' il codice del wifi")

    for testo, _ in FATTI:
        assert testo in prompt


async def test_con_cinquecento_fatti_il_contesto_resta_costante(con_ollama):
    """Il primo criterio di accettazione della scheda."""
    from shinra.infra.data_store import data_store

    for testo, categoria in FATTI:
        data_store.add_knowledge_item(testo, categoria)
    riempi(500)

    servizio = ServizioConoscenza()
    await servizio.aggiorna_indice()

    prompt = await servizio.per_la_domanda("dove si trova la caldaia")

    assert prompt.count("\n") + 1 <= dominio.MASSIMO_FATTI
    assert len(prompt) < 2000


async def test_e_recupera_comunque_quello_giusto(con_ollama):
    """Un contesto costante che non contiene la risposta sarebbe una
    regressione, non un miglioramento."""
    from shinra.infra.data_store import data_store

    for testo, categoria in FATTI:
        data_store.add_knowledge_item(testo, categoria)
    riempi(500)

    servizio = ServizioConoscenza()
    await servizio.aggiorna_indice()

    prompt = await servizio.per_la_domanda("dove si trova la caldaia")

    assert "cantina" in prompt


async def test_senza_embedding_si_recupera_per_testo(senza_ollama):
    """La casa risponde peggio, non smette di sapere."""
    from shinra.infra.data_store import data_store

    for testo, categoria in FATTI:
        data_store.add_knowledge_item(testo, categoria)
    riempi(100)

    servizio = ServizioConoscenza()
    await servizio.aggiorna_indice()

    prompt = await servizio.per_la_domanda("dove si trova la caldaia")

    assert "cantina" in prompt


async def test_l_indice_si_rifa_quando_un_fatto_cambia(con_ollama):
    """Senza, un fatto modificato resterebbe con il vettore del testo
    vecchio: non un errore, risposte sbagliate."""
    from shinra.infra.data_store import data_store

    voce = data_store.add_knowledge_item("La caldaia e' in cantina", "casa")
    servizio = ServizioConoscenza()
    await servizio.aggiorna_indice()

    prima = depositi.embedding.tutti()[voce["id"]]["impronta"]

    depositi.fatti.aggiorna(voce["id"], {"text": "La caldaia e' in soffitta"})
    await servizio.aggiorna_indice()

    dopo = depositi.embedding.tutti()[voce["id"]]["impronta"]
    assert dopo != prima


async def test_un_indice_gia_fatto_non_si_rifa(con_ollama):
    """Ricalcolare tutto a ogni avvio terrebbe Ollama occupato per niente
    mentre qualcuno sta parlando alla casa."""
    from shinra.infra.data_store import data_store

    data_store.add_knowledge_item("La caldaia e' in cantina", "casa")
    servizio = ServizioConoscenza()

    primo = await servizio.aggiorna_indice()
    secondo = await servizio.aggiorna_indice()

    assert primo["calcolati"] == 1
    assert secondo["calcolati"] == 0


async def test_un_fatto_cancellato_non_lascia_il_suo_vettore(con_ollama):
    """A ogni recupero si confronterebbe con qualcosa che la casa non sa
    piu'."""
    from shinra.infra.data_store import data_store

    voce = data_store.add_knowledge_item("La caldaia e' in cantina", "casa")
    servizio = ServizioConoscenza()
    await servizio.aggiorna_indice()
    assert depositi.embedding.conta() == 1

    depositi.fatti.cancella(voce["id"])
    esito = await servizio.aggiorna_indice()

    assert esito["orfani_tolti"] == 1
    assert depositi.embedding.conta() == 0


async def test_cambiare_modello_rifa_i_vettori(con_ollama, monkeypatch):
    """Vettori di modelli diversi vivono in spazi diversi, e confrontarli
    produce numeri che sembrano punteggi e non lo sono."""
    from shinra.infra.data_store import data_store
    from shinra.infra.llm import embedding

    data_store.add_knowledge_item("La caldaia e' in cantina", "casa")
    servizio = ServizioConoscenza()
    await servizio.aggiorna_indice()

    monkeypatch.setattr(embedding, "modello", lambda: "un-altro-modello")
    esito = await servizio.aggiorna_indice()

    assert esito["calcolati"] == 1


async def test_si_sa_quali_fatti_hanno_contribuito(con_ollama):
    """Quando l'assistente dice una cosa strana, la prima domanda e' «da
    dove l'ha presa»."""
    from shinra.infra.data_store import data_store

    for testo, categoria in FATTI:
        data_store.add_knowledge_item(testo, categoria)
    riempi(100)

    servizio = ServizioConoscenza()
    await servizio.aggiorna_indice()
    await servizio.per_la_domanda("dove si trova la caldaia")

    usati = servizio.fatti_usati()

    assert usati
    assert any("cantina" in u["testo"] for u in usati)
    assert all(0 <= u["punteggio"] <= 1 for u in usati)


async def test_lo_stato_dice_se_il_recupero_e_semantico(con_ollama):
    """`semantico: false` con dei fatti presenti vuol dire che il modello non
    e' installato: dirlo evita di credere che la ricerca funzioni male."""
    from shinra.infra.data_store import data_store

    data_store.add_knowledge_item("La caldaia e' in cantina", "casa")
    servizio = ServizioConoscenza()

    prima = await servizio.stato()
    assert prima["semantico"] is False
    assert prima["recupero_attivo"] is False

    await servizio.aggiorna_indice()
    dopo = await servizio.stato()

    assert dopo["semantico"] is True


async def test_senza_fatti_lo_dice(senza_ollama):
    servizio = ServizioConoscenza()

    assert "Nessuna informazione" in await servizio.per_la_domanda("qualunque cosa")
