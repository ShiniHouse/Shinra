# -*- coding: utf-8 -*-
"""I passi dell'intervista di apprendimento: una domanda, un'informazione.

Fino alla #209 ogni passo faceva tre domande in una («in quale citta', a che
piano, quante stanze»): chi risponde ne coglie una, e le altre due restano
ignote per sempre. Adesso una domanda ha un solo punto interrogativo, e un
test lo controlla sui testi.

Un passo puo' dire cosa la casa sa gia', in due modi:

- `noto`: una fonte che il database conosce davvero (`profili`, `stanze`);
- `parole`: parole che, trovate in un fatto gia' salvato della stessa
  categoria, dicono che quella domanda ha gia' una risposta.

Se la casa lo sa, la domanda non si rifa'. Cosa si sa lo decide
`intervista_noto`: le domande le sceglie il codice, il modello serve solo a
leggere la risposta libera.
"""

from typing import Any, Dict, List

INTERVIEW_STEPS: List[Dict[str, Any]] = [
    {
        "id": "casa_citta",
        "category": "casa",
        "title": "Dove si trova la casa",
        "question": "In quale città o zona si trova la tua casa?",
        "hint": "es. Vivo ad Arezzo.",
        "parole": ("vivo a", "abito a", "città", "citta", "zona", "si trova a", "si trova ad"),
    },
    {
        "id": "casa_piano",
        "category": "casa",
        "title": "Il piano",
        "question": "A che piano abiti?",
        "hint": "es. Al secondo piano di un condominio.",
        "parole": ("piano",),
    },
    {
        "id": "casa_stanze",
        "category": "casa",
        "title": "Le stanze",
        "question": "Quali sono le stanze principali della casa?",
        "hint": "es. Salotto, cucina, due camere e studio.",
        "noto": "stanze",
    },
    {
        "id": "famiglia_chi",
        "category": "famiglia",
        "title": "Chi vive in casa",
        "question": "Chi vive con te in casa?",
        "hint": "es. Mia moglie Sonia e i miei figli Thomas e Christian.",
        "noto": "profili",
    },
    {
        "id": "famiglia_stanze",
        "category": "famiglia",
        "title": "Dove sta ciascuno",
        "question": "In quale stanza passa più tempo ciascuno di loro?",
        "hint": "es. Thomas sta spesso nella cameretta.",
        "parole": ("passa più tempo", "sta spesso", "passa piu tempo"),
    },
    {
        "id": "mattina_ora",
        "category": "abitudini",
        "title": "L'ora del risveglio",
        "question": "A che ora ti svegli di solito?",
        "hint": "es. Mi sveglio alle 7:00.",
        "parole": ("sveglia", "si sveglia", "mi sveglio", "risveglio"),
    },
    {
        "id": "mattina_cosa",
        "category": "abitudini",
        "title": "Cosa succede al risveglio",
        "question": "Che cosa vorresti che succedesse in casa quando ti svegli?",
        "hint": "es. Accendere la luce in cucina e la macchina del caffè.",
    },
    {
        "id": "notte_ora",
        "category": "abitudini",
        "title": "L'ora di andare a dormire",
        "question": "A che ora vai a dormire di solito?",
        "hint": "es. Verso le 23:30.",
        "parole": ("va a letto", "vado a letto", "va a dormire", "vado a dormire"),
    },
    {
        "id": "notte_cosa",
        "category": "abitudini",
        "title": "Cosa succede la sera",
        "question": "Che cosa deve succedere in casa quando vai a dormire?",
        "hint": "es. Spegnere tutte le luci e abbassare il termostato a 18 gradi.",
    },
    {
        "id": "relax",
        "category": "abitudini",
        "title": "Relax e svago",
        "question": "Quando guardi un film, come ti piace impostare le luci del salotto?",
        "hint": "es. Le abbasso al 15% e accendo la presa della TV.",
    },
    {
        "id": "tecnico_wifi",
        "category": "casa_tecnica",
        "title": "La rete per gli ospiti",
        "question": "Qual è il nome della rete Wi-Fi per gli ospiti?",
        "hint": "es. CasaMia_Guest.",
        "parole": ("wi-fi", "wifi", "rete ospiti"),
    },
    {
        "id": "tecnico_contatore",
        "category": "casa_tecnica",
        "title": "Il contatore",
        "question": "Dove si trova il contatore elettrico?",
        "hint": "es. Nel sottoscala all'ingresso.",
        "parole": ("contatore",),
    },
    {
        "id": "tecnico_contatto",
        "category": "casa_tecnica",
        "title": "Un contatto importante",
        "question": "C'è un contatto importante da ricordare, come l'idraulico o il medico?",
        "hint": "es. L'idraulico è Rossi, 333 1234567.",
        "parole": ("idraulico", "elettricista", "medico", "numero di emergenza"),
    },
]
