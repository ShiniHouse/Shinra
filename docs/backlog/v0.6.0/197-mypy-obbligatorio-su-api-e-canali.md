---
title: "ci(tipi): mypy obbligatorio anche su api e channels"
issue: 197
milestone: "v0.6.0"
labels: ["tipo: attivita'", "area: infra"]
---

## Contesto

Nella CI mypy e' obbligatorio su `config`, `domain`, `infra`, `services` e
`skills`, e solo informativo su `api` e `channels`: proprio i livelli che
ricevono l'input esterno. Il passaggio a obbligatorio dipende da quanti
errori ci sono oggi, che va misurato prima.

## Cosa fare

- [x] Contare gli errori di mypy su `api` e `channels`
- [x] Correggerli, o annotarli uno per uno con il motivo, come si fa per le eccezioni di architettura
- [x] Togliere `continue-on-error` dal passo della CI

## Criteri di accettazione

- [x] Il passo della CI per `api` e `channels` e' obbligatorio e verde
- [x] Gli errori rimasti sono soppressi uno per uno, con la ragione accanto

## Com'e' andata

Gli errori erano **due, in un file solo** (`channels/alexa/verifica_firma.py`): meno di
quanto si temesse, e uno dei due era un difetto vero.

- `get_values_for_type` su una estensione tipizzata come generica: si chiedeva l'estensione
  per OID invece che per classe. Corretto con `get_extension_for_class`.
- **`verify(..., None)`**: un certificato firmato con Ed25519 non ha `signature_hash_algorithm`,
  e passarlo a `verify` sollevava un `TypeError` che nessuno gestiva. Su un endpoint pubblico
  (`/api/alexa`) vuol dire un **500** a una richiesta con un certificato strano, e un 500 che
  racconta che la verifica e' arrivata fin li'. Adesso e' un rifiuto come gli altri; un test
  costruisce un certificato Ed25519 vero e verifica che prima falliva (`TypeError`) e ora no.

Nessun errore e' stato soppresso: non ce n'e' bisogno. La CI e' obbligatoria su tutto
`src/shinra` (132 file), e il comando in `docs/SVILUPPO.md` e' diventato `mypy src/shinra`.
