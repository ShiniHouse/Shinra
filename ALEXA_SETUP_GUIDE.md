# 🎙️ Guida Integrazione Amazon Alexa / Echo con Shinra

Questa guida ti mostra come creare una **Skill Alexa personalizzata** per parlare con il tuo assistente **Shinra** dai tuoi dispositivi Echo, dicendo semplicemente *"Alexa, apri Shinra"*.

---

## 1. Requisiti
1. Un account [Amazon Developer](https://developer.amazon.com/alexa/console/ask) (gratuito, stesso account dei tuoi Echo).
2. Il server Shinra avviato sul tuo PC (`.\.venv\Scripts\python.exe run.py`).
3. Un tunnel HTTPS per rendere raggiungibile il server da internet (es. **Cloudflare Tunnel** o **ngrok**).

---

## 2. Esporre Shinra su HTTPS (Tunnel)
Poiché Alexa richiede un endpoint HTTPS pubblico:

### Opzione A: Cloudflare Tunnel (Consigliato — gratuito e illimitato)
```powershell
cloudflared tunnel --url http://localhost:8000
```
Otterrai un URL del tipo: `https://tuo-nome.trycloudflare.com`

### Opzione B: ngrok
```powershell
ngrok http 8000
```
Otterrai un URL del tipo: `https://abc123xyz.ngrok-free.app`

Il tuo endpoint Alexa sarà:
`https://<TUO_URL_TUNNEL>/api/alexa`

---

## 3. Creazione della Skill su Amazon Developer Console

1. Accedi: **[developer.amazon.com/alexa/console/ask](https://developer.amazon.com/alexa/console/ask)**
2. Clicca **Create Skill** e configura:
   - **Skill name**: `Shinra`
   - **Primary locale**: `Italian (IT)`
   - **Experience**: `Other` → `Custom`
   - **Hosting service**: `Provision your own`
3. Clicca **Create Skill**.

### 4. Interaction Model (JSON Editor)
Nel menu laterale: **Invocations → Skill Invocation Name** → inserisci: `shinra`

Poi vai su **Intents → JSON Editor** e incolla:

```json
{
  "interactionModel": {
    "languageModel": {
      "invocationName": "shinra",
      "intents": [
        { "name": "AMAZON.CancelIntent", "samples": [] },
        { "name": "AMAZON.HelpIntent", "samples": [] },
        { "name": "AMAZON.StopIntent", "samples": [] },
        { "name": "AMAZON.NavigateHomeIntent", "samples": [] },
        {
          "name": "CustomCommandIntent",
          "slots": [
            { "name": "query", "type": "AMAZON.SearchQuery" }
          ],
          "samples": [
            "{query}",
            "chiedi {query}",
            "dimmi {query}",
            "controlla {query}",
            "attiva {query}",
            "meteo {query}"
          ]
        }
      ],
      "types": []
    }
  }
}
```

Clicca **Save Model** → **Build Model** (circa 30 secondi).

---

## 5. Configurare l'Endpoint HTTPS

1. Menu laterale → **Endpoint**.
2. Seleziona **HTTPS**.
3. Nel campo **Default Region** incolla:
   `https://<TUO_URL_TUNNEL>/api/alexa`
4. Certificato SSL:
   - Con Cloudflare/ngrok: *"My development endpoint is a sub-domain of a domain that has a wildcard certificate from a certificate authority"*.
5. Clicca **Save Endpoints**.

---

## 6. Testare con Alexa

1. Scheda **Test** → imposta il selettore su **"Development"**.
2. Prova a dire o digitare:
   - *"apri shinra"* → Shinra risponde: *"Alessio. Sono online."*
   - *"chiedi a shinra che tempo farà domani"*
   - *"chiedi a shinra le ultime notizie dal mondo"*
   - *"chiedi a shinra cosa significa olocausto"*
   - *"chiedi a shinra di accendere le luci del salotto"*

Tutti i tuoi dispositivi **Amazon Echo** collegati allo stesso account avranno automaticamente la Skill attiva in modalità sviluppo.
