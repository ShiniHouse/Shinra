# 🎙️ Guida Definitiva: Configurazione e Modifica della Skill Alexa per Shinra

Questa guida ti spiega passo dopo passo come configurare, testare e **modificare in futuro** la tua Skill Alexa personalizzata per interagire con il tuo assistente domestico **Shinra** tramite qualsiasi dispositivo **Amazon Echo** o dall'app per smartphone.

---

## 📑 Indice
1. [Requisiti e Architettura](#1-requisiti-e-architettura)
2. [Creazione della Skill](#2-creazione-della-skill)
3. [Interaction Model Completo (JSON Editor)](#3-interaction-model-completo-json-editor)
4. [Configurazione Endpoint HTTPS & SSL](#4-configurazione-endpoint-https--ssl)
5. [Impostazioni di Rete (NPM e Cloudflare WAF)](#5-impostazioni-di-rete-npm-e-cloudflare-waf)
6. [Come Usare e Testare la Skill](#6-come-usare-e-testare-la-skill)
7. [🪄 Come Modificare la Skill in Futuro](#7--come-modificare-la-skill-in-futuro)
8. [Risoluzione Errori Comuni](#8-risoluzione-errori-comuni)

---

## 1. Requisiti e Architettura
* Un account **[Amazon Developer](https://developer.amazon.com/alexa/console/ask)** (gratuito, registrato con la stessa email dei tuoi dispositivi Amazon Echo).
* Il backend Shinra attivo su Debian (`https://shinra.guidelli.net/api/alexa`).
* Certificato SSL valido tramite Cloudflare / Let's Encrypt.

---

## 2. Creazione della Skill
1. Accedi alla console: **[developer.amazon.com/alexa/console/ask](https://developer.amazon.com/alexa/console/ask)**.
2. In basso a destra clicca su **`Alexa Skills Kit`** ➔ poi clicca su **`Create Skill`**.
3. Compila la prima schermata:
   * **Skill Name**: `Shinra`
   * **Primary Locale**: `Italian (IT)`
   * **Experience / Type**: Seleziona **`Other`** ➔ poi **`Custom`**
   * **Hosting Service**: Seleziona **`Provision your own`**
4. Clicca su **Next** (in alto a destra), seleziona il template **"Start from Scratch"** e conferma con **Create Skill**.

---

## 3. Interaction Model Completo (JSON Editor)

Nel menu a sinistra della console Alexa:
1. Vai su **Interaction Model** ➔ **JSON Editor**.
2. Cancella tutto e incolla questo schema JSON validato (che include tutte le *carrier phrases* obbligatorie per evitare errori di build):

```json
{
  "interactionModel": {
    "languageModel": {
      "invocationName": "shinra",
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
            "quando e {query}",
            "quando è {query}",
            "chi {query}",
            "chi e {query}",
            "chi è {query}",
            "dove {query}",
            "perché {query}",
            "perche {query}",
            "quanto {query}",
            "quanti {query}",
            "qual è {query}",
            "qual e {query}",
            "imposta {query}",
            "accendi {query}",
            "spegni {query}",
            "cerca {query}",
            "spiegami {query}",
            "fammi {query}",
            "apri {query}",
            "chiudi {query}",
            "domanda {query}"
          ]
        }
      ],
      "types": []
    }
  }
}
```

3. Clicca su **"Save Model"** e poi su **"Build Model"**. Attendi la notifica verde **"Build Successful"**.

---

## 4. Configurazione Endpoint HTTPS & SSL

1. Nel menu a sinistra clicca su **Endpoint**.
2. Seleziona il pallino **HTTPS**.
3. Incolla il tuo URL in entrambi i campi:
   * **Default Region**: `https://shinra.guidelli.net/api/alexa`
   * **Europe and India (Europe)**: `https://shinra.guidelli.net/api/alexa`
4. Nel menu a tendina *Select SSL certificate type* seleziona per entrambi la **2ª opzione**:
   * **`My development endpoint is a sub-domain of a domain that has a wildcard certificate from a certificate authority`**
5. Clicca sul pulsante azzurro **"Save Endpoints"** in alto a destra.

---

## 5. Impostazioni di Rete (NPM e Cloudflare WAF)

Affinché i server di Amazon Alexa possano comunicare con il tuo server di casa senza essere bloccati:

### A. Su Nginx Proxy Manager (NPM):
* Nel Proxy Host di `shinra.guidelli.net`:
* **Block Common Exploits**: ⚠️ **DISATTIVATO** (evita che Nginx blocchi le chiamate interne di Alexa con un errore 403).
* **Force SSL**: Attivo.
* **HTTP/2 Support**: Attivo.

### B. Su Cloudflare Dashboard:
* Vai su **Security** ➔ **WAF** ➔ **Custom Rules**.
* Crea una regola:
  * **Nome**: `Allow Alexa Endpoint`
  * **Campo (Field)**: `URI Path` | **Operatore**: `equals` | **Valore**: `/api/alexa`
  * **Azione**: `Skip` ➔ Seleziona tutte le opzioni (WAF, Bot Fight Mode, Rate Limiting).

---

## 6. Come Usare e Testare la Skill

### A. Nel Simulatore Web (Tab "Test"):
* Vai nella scheda **Test** in alto.
* Imposta il selettore da *Off* a **Development**.
* Scrivi: **`apri shinra`** *(non scrivere la parola "alexa", il simulatore è già Alexa!)*.
* Shinra risponderà: *"Shinra online. Con chi parlo?"*.
* Rispondi con il tuo nome: **`Alessio`** ➔ *"Alessio. Dimmi."*.

### B. Sui tuoi dispositivi fisici Amazon Echo:
Tutti gli Echo collegati al tuo account sono già abilitati:
* **Comando Diretto (One-Shot)**:
  * *"Alexa, chiedi a Shinra che tempo farà domani a Roma"*
  * *"Alexa, dì a Shinra di accendere la luce in sala"*
  * *"Alexa, chiedi a Shinra cosa significa il termine olocausto"*
  * *"Alexa, chiedi a Shinra le ultime notizie"*
* **Sessione Continua**:
  * Dici *"Alexa, apri Shinra"* ➔ l'anello luminoso resta blu e puoi fare domande consecutive senza dover ripetere la parola "Alexa".

### C. Creare una Routine con 1 sola parola (*"Alexa, Shinra"*):
1. Apri l'app **Amazon Alexa** su smartphone.
2. Vai su **Altro** ➔ **Routine** ➔ premi **`+`**.
3. **Quando:** seleziona *Voce* ➔ imposta la parola (es. `Shinra`).
4. **Aggiungi un'azione:** seleziona *Personalizzata* ➔ scrivi `apri Shinra`.
5. Salva la routine. Ora basterà dire: **"Alexa, Shinra"**!

---

## 7. 🪄 Come Modificare la Skill in Futuro

Se in futuro vuoi aggiornare o personalizzare la Skill:

### A. Aggiungere nuove frasi di comando (Sample Utterances):
1. Vai su **Interaction Model** ➔ **Intents** ➔ clicca su **`GeneralQueryIntent`**.
2. Nel riquadro *Sample Utterances* aggiungi nuove combinazioni contenenti lo slot `{query}`, ad esempio:
   * `regola {query}`
   * `controlla {query}`
   * `attiva la modalità {query}`
3. Clicca su **"Save Model"** e poi su **"Build Model"**.

### B. Cambiare il nome di invocazione (*Invocation Name*):
1. Vai su **Interaction Model** ➔ **Invocations** ➔ **Skill Invocation Name**.
2. Modifica il nome (es. da `shinra` a `computer` o `casa`).
3. Clicca **"Save Model"** ➔ **"Build Model"**.

### C. Aggiornare l'URL del server:
1. Se cambi dominio o IP, vai su **Endpoint**.
2. Sostituisci l'URL nei campi *Default Region* ed *Europe and India*.
3. Clicca su **"Save Endpoints"**.

---

## 8. Risoluzione Errori Comuni

| Errore | Causa | Soluzione |
| :--- | :--- | :--- |
| **`Sample utterance "{query}" must include a carrier phrase`** | Amazon non consente lo slot `{query}` isolato. | Usa sempre frasi con prefisso come `dimmi {query}`, `chiedi {query}`, `esegui {query}` nel JSON Editor. |
| **`Non posso raggiungere la Skill richiesta`** | Cloudflare WAF, Nginx Proxy Manager o certificato SSL errato. | Disattiva *Block Common Exploits* in NPM, crea la regola di bypass WAF su Cloudflare per `/api/alexa` e seleziona la 2ª opzione SSL (*Wildcard certificate*). |
| **Timeout durante l'elaborazione su Echo** | Alexa richiede risposte entro 8 secondi. | Assicurati che Shinra usi `qwen2.5:3b` con `max_tokens: 150` in modo da rispondere in 1-2 secondi. |

