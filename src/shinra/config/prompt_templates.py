import datetime
from typing import Any, Optional

from shinra.config.settings import settings
from shinra.services.user_manager import UserProfile


def get_system_prompt(
    lingua: Any,
    default_city: str = "Roma",
    user_profile: Optional[UserProfile] = None,
    device_aliases: str = "",
    modes_summary: str = "",
) -> str:
    """Il prompt di sistema, nella lingua di chi sta parlando: la parte che non cambia fra una richiesta e l'altra.

    Ollama riusa il prefisso del prompt che ha gia' letto (nel banco, 130 s diventano 3-10 s), ma solo
    fino al primo byte diverso. Per questo qui non c'e' niente che cambi a ogni richiesta: la data e
    l'ora, lo stato dei dispositivi e i fatti recuperati per la domanda stanno in
    `get_contesto_della_richiesta`, che l'agente mette davanti alla frase dell'utente, dopo il prompt
    e dopo gli schemi degli strumenti. Prima l'ora, con i minuti, era alla prima riga: la cache
    moriva ogni minuto.

    `lingua` (un `Schemi`) la sceglie il chiamante, l'agente, che sa chi sta
    parlando; qui non si importa il caricatore perche' `config/` sta sotto
    `services/`, e si tipizza `Any` per la stessa ragione.

    I pezzi stanno nel file della lingua (`infra/lingue/`), non qui:
    il modello risponde nella lingua in cui gli si parla, quindi un prompt
    italiano davanti a una persona che scrive in inglese darebbe risposte in
    un italiano incerto. La lingua e' quella del profilo, se l'ha scelta; se
    no, quella dell'installazione (issue #36).
    """
    assistant_name = getattr(settings.assistant, "name", "Kyra") or "Kyra"
    user_name = user_profile.name if user_profile else lingua.prompt_di("utente_anonimo")
    age_group = user_profile.age_group if user_profile else "adult"
    role = user_profile.role if user_profile else "adult"

    if age_group == "child":
        persona = lingua.prompt_di("persona_bambino", nome=user_name)
    elif age_group == "teen":
        persona = lingua.prompt_di("persona_ragazzo", nome=user_name)
    else:
        ruolo = lingua.prompt_di("ruolo_admin" if role == "admin" else "ruolo_adulto")
        persona = lingua.prompt_di("persona_adulto", nome=user_name, ruolo=ruolo)

    parts = [
        lingua.prompt_di("intro", assistente=assistant_name, citta=default_city),
        persona,
        lingua.prompt_di("regole", citta=default_city),
    ]

    if device_aliases:
        parts.append(f"{lingua.prompt_di('titolo_alias')}:\n{device_aliases}")
    if modes_summary:
        parts.append(f"{lingua.prompt_di('titolo_modalita')}:\n{modes_summary}")

    return "\n\n".join(parts)


def get_contesto_della_richiesta(
    lingua: Any,
    home_context_summary: str = "",
    custom_knowledge: str = "",
    adesso: Optional[datetime.datetime] = None,
) -> str:
    """Quello che cambia a ogni richiesta: che ora e', cosa sa la casa, cosa serve per questa domanda.

    Va davanti alla frase dell'utente, nello stesso messaggio, e non nel prompt di sistema: vedi
    `get_system_prompt`.
    """
    parts = [lingua.prompt_di("adesso", adesso=lingua.data_e_ora(adesso or datetime.datetime.now()))]
    if custom_knowledge:
        parts.append(f"{lingua.prompt_di('titolo_conoscenza')}:\n{custom_knowledge}")
    if home_context_summary:
        parts.append(f"{lingua.prompt_di('titolo_dispositivi')}: {home_context_summary}")
    return "\n\n".join(parts)
