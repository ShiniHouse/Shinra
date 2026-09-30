import datetime
from typing import Any, Optional

from shinra.config.settings import settings
from shinra.services.user_manager import UserProfile


def get_system_prompt(
    lingua: Any,
    home_context_summary: str = "",
    default_city: str = "Roma",
    user_profile: Optional[UserProfile] = None,
    custom_knowledge: str = "",
    device_aliases: str = "",
    modes_summary: str = "",
) -> str:
    """Il prompt di sistema, nella lingua di chi sta parlando.

    `lingua` (un `Schemi`) la sceglie il chiamante, l'agente, che sa chi sta
    parlando; qui non si importa il caricatore perche' `config/` sta sotto
    `services/`, e si tipizza `Any` per la stessa ragione.

    I pezzi stanno nel file della lingua (`services/intenti/lingue/`), non qui:
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
        lingua.prompt_di(
            "intro",
            assistente=assistant_name,
            adesso=lingua.data_e_ora(datetime.datetime.now()),
            citta=default_city,
        ),
        persona,
        lingua.prompt_di("regole", citta=default_city),
    ]

    if custom_knowledge:
        parts.append(f"{lingua.prompt_di('titolo_conoscenza')}:\n{custom_knowledge}")
    if device_aliases:
        parts.append(f"{lingua.prompt_di('titolo_alias')}:\n{device_aliases}")
    if modes_summary:
        parts.append(f"{lingua.prompt_di('titolo_modalita')}:\n{modes_summary}")
    if home_context_summary:
        parts.append(f"{lingua.prompt_di('titolo_dispositivi')}: {home_context_summary}")

    return "\n\n".join(parts)
