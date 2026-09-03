# 🎙️ Guida Definitiva: Configurazione Skill Alexa per Kyra

Questa guida ti spiega come configurare e testare la tua Skill Alexa personalizzata con il nome di invocazione **Kyra** (molto più facile e naturale da pronunciare rispetto a Shinra per il riconoscimento vocale di Amazon Echo).

---

## 📑 Indice
1. [Perché Kyra risolve i problemi di pronuncia](#1-perché-kyra-risolve-i-problemi-di-pronuncia)
2. [Interaction Model Completo (JSON Editor)](#2-interaction-model-completo-json-editor)
3. [Come Aggiornare la Skill su Amazon Developer Console](#3-come-aggiornare-la-skill-su-amazon-developer-console)
4. [Configurazione Endpoint HTTPS](#4-configurazione-endpoint-https)
5. [Come Usare e Testare Kyra](#5-come-usare-e-testare-kyra)
6. [Consiglio Pro: Routine con 1 parola ("Alexa, Kyra")](#6-consiglio-pro-routine-con-1-parola-alexa-kyra)

---

## 1. Perché Kyra risolve i problemi di pronuncia

Amazon Alexa in lingua italiana ha difficoltà con fonemi non tipicamente italiani come *"Shinra"* (che viene spesso storpiato in *"scena"*, *"siringa"*, *"scimmia"* o interpretato come ricerca brani su Spotify).

**Kyra** (pronunciato *Chì-ra* o *Kì-ra*) ha invece due sillabe aperte e nette (`KI` + `RA`) che l'algoritmo vocale di Alexa riconosce al primo colpo, sia pronunciato veloce che sottovoce.

> [!TIP]
> Puoi impostare il nome di invocazione come **`kyra`** (oppure **`kira`** se preferisci la grafia fonetica italiana tradizionale). Entrambe le varianti sono pienamente gestite dal backend.

---

## 2. Interaction Model Completo (JSON Editor)

Questo schema JSON include gli intenti dedicati per **accendere/spegnere dispositivi domotici senza perdere i verbi d'azione**, attivare routine e porre qualsiasi domanda generica:

```json
{
  "interactionModel": {
    "languageModel": {
      "invocationName": "kyra",
      "intents": [
        {
          "name": "AMAZON.CancelIntent",
          "samples": []
        },
        {
          "name": "AMAZON.HelpIntent",
          "samples": []
        },
        {
          "name": "AMAZON.StopIntent",
          "samples": []
        },
        {
          "name": "AMAZON.NavigateHomeIntent",
          "samples": []
        },
        {
          "name": "AMAZON.FallbackIntent",
          "samples": []
        },
        {
          "name": "TurnOnIntent",
          "slots": [
            {
              "name": "device",
              "type": "AMAZON.SearchQuery"
            }
          ],
          "samples": [
            "accendi {device}",
            "attiva {device}",
            "apri {device}",
            "accendere {device}",
            "attivare {device}"
          ]
        },
        {
          "name": "TurnOffIntent",
          "slots": [
            {
              "name": "device",
              "type": "AMAZON.SearchQuery"
            }
          ],
          "samples": [
            "spegni {device}",
            "disattiva {device}",
            "chiudi {device}",
            "spegnere {device}",
            "disattivare {device}"
          ]
        },
        {
          "name": "ActivateModeIntent",
          "slots": [
            {
              "name": "mode",
              "type": "AMAZON.SearchQuery"
            }
          ],
          "samples": [
            "modalità {mode}",
            "modalita {mode}",
            "avvia {mode}",
            "imposta {mode}",
            "attiva modalità {mode}",
            "attiva modalita {mode}"
          ]
        },
        {
          "name": "GeneralQueryIntent",
          "slots": [
            {
              "name": "query",
              "type": "AMAZON.SearchQuery"
            }
          ],
          "samples": [
            "dimmi {query}",
            "chiedi {query}",
            "fai {query}",
            "esegui {query}",
            "cosa {query}",
            "come {query}",
            "quando {query}",
            "chi {query}",
            "dove {query}",
            "perché {query}",
            "perche {query}",
            "quanto {query}",
            "quanti {query}",
            "qual è {query}",
            "qual e {query}",
            "cerca {query}",
            "spiegami {query}",
            "fammi {query}",
            "domanda {query}",
            "voglio {query}",
            "vorrei {query}",
            "puoi {query}"
          ]
        }
      ],
      "types": []
    }
  }
}
```

---

## 3. Come Aggiornare la Skill su Amazon Developer Console

Se hai già creato la Skill:

1. Apri **[developer.amazon.com/alexa/console/ask](https://developer.amazon.com/alexa/console/ask)** ed entra nella tua Skill.
2. Nel menu a sinistra vai su **Interaction Model** ➔ **JSON Editor**.
3. Seleziona tutto il testo presente, cancellalo e incolla il JSON completo qui sopra.
4. Clicca sul pulsante in alto **"Save Model"**.
5. Clicca subito dopo su **"Build Model"** e attendi qualche secondo fino a quando compare il messaggio verde **"Build Successful"**.

Se vuoi cambiare anche il nome visualizzato della skill:
* Vai su **Skill Preview / Distribution** ➔ **Skill Name** e imposta `Kyra`.

---

## 4. Configurazione Endpoint HTTPS

Nel menu a sinistra su **Endpoint**:
* Seleziona **HTTPS**.
* **Default Region**: `https://tuodominio.com/api/alexa`
* **Europe and India**: `https://tuodominio.com/api/alexa`
* Tipo di certificato: Seleziona la 2ª opzione (*"My development endpoint is a sub-domain of a domain that has a wildcard certificate from a certificate authority"*).
* Clicca su **"Save Endpoints"**.

---

## 5. Come Usare e Testare Kyra

### A. Apertura Continua (Consigliata)
> **"Alexa, apri Kyra"**

Alexa risponderà: *"Kyra online, Alessio. Dimmi pure."* e l'anello luminoso rimarrà blu in ascolto. Da questo momento puoi impartire comandi naturali direttamente:
* *"Accendi la luce in cucina"*
* *"Che tempo fa oggi?"*
* *"Ultime notizie"*
* *"Modalità Relax"*

### B. Comando One-Shot Diretto
> **"Alexa, chiedi a Kyra che tempo fa a Roma"**  
> **"Alexa, dì a Kyra di accendere il salotto"**  
> **"Alexa, chiedi a Kyra le notizie del giorno"**

---

## 6. Consiglio Pro: Routine con 1 parola ("Alexa, Kyra")

Per non dover dire ogni volta *"Alexa, apri Kyra"*:
1. Apri l'app **Amazon Alexa** sullo smartphone.
2. Vai su **Altro** ➔ **Routine** ➔ premi **`+`**.
3. **Quando:** seleziona *Voce* ➔ scrivi **`Kyra`**.
4. **Aggiungi un'azione:** seleziona *Personalizzata* ➔ scrivi **`apri Kyra`**.
5. Salva la routine.

Ora basterà dire semplicemente: **"Alexa, Kyra"** e partirà subito!
