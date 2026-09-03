---
title: "security(config): sposta i segreti fuori dal repository"
milestone: "v0.1.0"
labels: ["tipo: difetto", "area: sicurezza", "area: infra", "gravita': alta"]
riferimento: SEC-05
priorita: "Da fare per prima nella milestone"
---

## Contesto

`config/config.yaml` **e' tracciato da git**, e `config/settings.py:65`
(`save_config`) ci scrive dentro il token a lungo termine di Home Assistant e il
PIN amministratore ogni volta che si salvano le impostazioni dall'interfaccia.

La cronologia oggi e' pulita: contiene solo il segnaposto. Ma il prossimo
`git commit -a` dopo una modifica dalle impostazioni pubblica le credenziali di
casa su un repository GitHub pubblico. E' una mina gia' armata.

Stesso problema per `data/users.json` e `data/knowledge.json`, che contengono
nomi, abitudini e dati personali della famiglia e sono anch'essi versionati.

> Questa issue va chiusa **per prima**: il controllo «segreti» della CI fallisce
> finche' i file restano tracciati.

## Cosa fare

- [ ] `git rm --cached config/config.yaml data/users.json data/knowledge.json data/timers.json`
- [ ] Verificare che `.gitignore` li copra (gia' aggiornato)
- [ ] Spostare i dati di seed generici in `data/examples/` e far generare i file runtime al primo avvio se assenti
- [ ] Introdurre `pydantic-settings`: i segreti si leggono da `.env` o dall'ambiente, mai da `config.yaml`
- [ ] `save_config()` non deve mai scrivere un segreto su disco in chiaro
- [ ] Aggiungere alla configurazione un controllo d'avvio che rifiuta di partire se il token Home Assistant e' ancora il segnaposto e `home_assistant.enabled` e' vero
- [ ] Documentare la procedura in `README.md` e in `CONTRIBUTING.md`

## Criteri di accettazione

- [ ] `git ls-files` non elenca `config/config.yaml` ne' alcun file con dati personali
- [ ] Il job «Controllo segreti» della CI e' verde
- [ ] Una installazione da zero funziona seguendo solo `.env.example`
- [ ] Il gancio pre-commit blocca un tentativo di committare `config/config.yaml`

## Nota sulla cronologia

La cronologia e' stata verificata e **non contiene credenziali reali**: nessuna
riscrittura con `git filter-repo` e' necessaria. Se in futuro un segreto dovesse
finire in un commit, va prima revocato in Home Assistant e poi rimosso dalla
cronologia — in quest'ordine.
