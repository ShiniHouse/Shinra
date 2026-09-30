"""Liste, calendario e scadenze di manutenzione (issue #25)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from shinra.skills.calendario import aggiungi_impegno, impegni, prossimi_impegni
from shinra.skills.liste import aggiungi_a_lista, leggi_lista, quali_liste, togli_da_lista
from shinra.skills.manutenzione import (
    aggiungi_scadenza,
    dimentica_scadenza,
    scadenze_in_arrivo,
    segna_fatta,
)

GESTORI: Dict[str, Callable] = {
    "aggiungi_a_lista": aggiungi_a_lista,
    "leggi_lista": leggi_lista,
    "togli_da_lista": togli_da_lista,
    "quali_liste": quali_liste,
    "impegni": impegni,
    "prossimi_impegni": prossimi_impegni,
    "aggiungi_impegno": aggiungi_impegno,
    "aggiungi_scadenza": aggiungi_scadenza,
    "scadenze_in_arrivo": scadenze_in_arrivo,
    "segna_fatta": segna_fatta,
    "dimentica_scadenza": dimentica_scadenza,
}

SCHEMI: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "aggiungi_a_lista",
            "description": (
                "Aggiunge una o piu' voci a una lista (spesa, cose da fare, o altre). "
                "«Latte, pane e uova» sono tre voci. Se in Home Assistant c'e' una "
                "lista todo, scrive li'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "voce": {
                        "type": "string",
                        "description": "Cosa aggiungere. Piu' cose separate da virgole o «e».",
                    },
                    "lista": {"type": "string", "description": "Quale lista. Omessa, e' la spesa."},
                },
                "required": ["voce"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leggi_lista",
            "description": "Dice cosa c'e' in una lista.",
            "parameters": {
                "type": "object",
                "properties": {"lista": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "togli_da_lista",
            "description": "Spunta una voce da una lista: comprata, o fatta.",
            "parameters": {
                "type": "object",
                "properties": {"voce": {"type": "string"}, "lista": {"type": "string"}},
                "required": ["voce"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quali_liste",
            "description": "Elenca le liste esistenti, sia quelle di Home Assistant sia quelle di casa.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "impegni",
            "description": (
                "Gli impegni di un giorno — «cosa ho oggi», «cosa ho domani», «cosa "
                "ho sabato» — presi da tutti i calendari messi insieme."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "quando_detto": {"type": "string", "description": "«oggi», «domani», «sabato», «il 22»."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prossimi_impegni",
            "description": "Cosa c'e' nei prossimi giorni, giorno per giorno.",
            "parameters": {
                "type": "object",
                "properties": {
                    "giorni": {"type": "integer", "description": "Quanti giorni guardare, default 7."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggiungi_impegno",
            "description": (
                "Segna un impegno sul calendario di casa. NON scrive sui calendari di "
                "Home Assistant, che sono di Google o iCloud e appartengono a chi li "
                "possiede. Serve sempre un quando: se manca, il tool lo chiede e non "
                "crea niente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "titolo": {"type": "string"},
                    "quando_detto": {"type": "string", "description": "«domani alle 15», «sabato», «il 22»."},
                    "luogo": {"type": "string"},
                    "tutto_il_giorno": {"type": "boolean"},
                },
                "required": ["titolo", "quando_detto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggiungi_scadenza",
            "description": (
                "Segna una scadenza di casa: filtri della caldaia, revisione, bollo, "
                "garanzia. Se ricorre, `ogni` e `unita` dicono ogni quanto. Quando si "
                "avvicina, la casa crea da sola un promemoria che suona."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "titolo": {"type": "string"},
                    "quando_detto": {
                        "type": "string",
                        "description": "Quando scade: «il 15 marzo», «fra sei mesi».",
                    },
                    "ogni": {"type": "integer", "description": "Ogni quanto torna. 0 se non torna."},
                    "unita": {"type": "string", "enum": ["giorni", "mesi", "anni"]},
                    "preavviso": {
                        "type": "integer",
                        "description": "Quanti giorni prima avvisare. Default 7.",
                    },
                    "documento": {"type": "string", "description": "Dove sta la garanzia o la fattura."},
                },
                "required": ["titolo", "quando_detto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scadenze_in_arrivo",
            "description": "Cosa scade e cosa e' gia' scaduto. Le due cose vengono dette separate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "giorni": {"type": "integer", "description": "Quanti giorni guardare avanti."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "segna_fatta",
            "description": (
                "Segna una scadenza come fatta. Se ricorre, la prossima si conta da "
                "oggi — non dalla data prevista, altrimenti ogni ritardo si accumula."
            ),
            "parameters": {
                "type": "object",
                "properties": {"titolo": {"type": "string"}},
                "required": ["titolo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dimentica_scadenza",
            "description": "Toglie una scadenza.",
            "parameters": {
                "type": "object",
                "properties": {"titolo": {"type": "string"}},
                "required": ["titolo"],
            },
        },
    },
]
