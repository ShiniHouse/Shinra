# Banco di prova del tool calling — 2026-10-02

- **Macchina:** non dichiarata
- **Ripetizioni per richiesta:** 1
- **Revisione:** `c7454d2`

## Stato della macchina e limiti del servizio (all'inizio del giro)

- **Core logici:** 6
- **Memoria:** 7.2 GB disponibili su 15.4 GB
- **Swap:** 657 MB in uso su 977 MB
- **Carico (1/5/15 min):** 0.69 / 0.58 / 0.55
- **Ollama: CPU concessa (secondi di CPU al secondo):** 5s
- **Ollama: priorita' (Nice):** 5
- **Ollama: tetto di memoria:** 6.0 GB
- **Processi piu' grandi:** java 4.0 GB, python 0.6 GB, firefox-esr 0.5 GB, WebExtensions 0.5 GB, gnome-shell 0.3 GB

I criteri sono una **proposta** per l'ADR 0008, non una verita': strumento_giusto ≥ 85.0, argomenti_giusti ≥ 75.0, inventate ≤ 1, cicli ≤ 0, mediana_secondi ≤ 8.0.

Le percentuali sono sulle richieste **che hanno avuto una risposta**: un timeout o un guasto di Ollama sono un dato mancante, non uno strumento sbagliato. Con meno del 90% di risposte la riga e' **n.v.** (non valutabile).

| Configurazione | Risposte | Strumento giusto | Argomenti giusti | Inventate | Cicli | Troncati | Token prompt | Mediana s | p90 s | Regge |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| qwen2.5:3b @ 1024 | 6/6 | 0.0% | 0.0% | 0 | 0 | 6/6 | 514 | 14.69 | 16.6 | no |

## Per categoria (riuscite / con risposta)

| Categoria | qwen2.5:3b @ 1024 |
| :--- | ---: |
| casa | 0/6 |

## Dove sbaglia: qwen2.5:3b @ 1024

- «accendi la luce della cucina» — atteso control_device; visto nessuno strumento
- «spegni la luce del salotto» — atteso control_device; visto nessuno strumento
- «metti la luce della camera al 30 per cento» — atteso control_device; visto nessuno strumento
- «accendi la luce dello studio di colore blu» — atteso control_device; visto nessuno strumento
- «accendi la caffettiera» — atteso control_device; visto nessuno strumento
- «spegni la presa della caffettiera» — atteso control_device; visto nessuno strumento
