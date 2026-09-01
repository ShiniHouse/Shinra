import datetime
from typing import Optional
from core.user_manager import UserProfile

def get_system_prompt(
    home_context_summary: str = "",
    default_city: str = "Roma",
    user_profile: Optional[UserProfile] = None,
    custom_knowledge: str = "",
    device_aliases: str = "",
    modes_summary: str = ""
) -> str:
    now_str = datetime.datetime.now().strftime("%A %d %B %Y, ore %H:%M")
    user_name = user_profile.name if user_profile else "Utente"
    age_group = user_profile.age_group if user_profile else "adult"
    role = user_profile.role if user_profile else "adult"

    if age_group == "child":
        persona = f"Parli con il bambino {user_name}. Usa linguaggio semplice, allegro e rassicurante. Niente contenuti violenti o complessi."
    elif age_group == "teen":
        persona = f"Parli con il ragazzo {user_name}. Sii pratico, diretto e chiaro."
    else:
        persona = f"Parli con {user_name} ({'Amministratore' if role == 'admin' else 'Adulto'}). Stile Jarvis: cordiale, riservato, preciso, risposte brevi e naturali in italiano. Evita frasi verbose."

    parts = [
        f"Sei Shinra, assistente domestico di casa. Oggi è {now_str}. Città: {default_city}.",
        persona,
    ]

    if custom_knowledge:
        parts.append(f"CONOSCENZA CASA:\n{custom_knowledge}")
    if device_aliases:
        parts.append(f"ALIAS DISPOSITIVI:\n{device_aliases}")
    if modes_summary:
        parts.append(f"MODALITÀ:\n{modes_summary}")
    if home_context_summary:
        parts.append(f"DISPOSITIVI ATTIVI: {home_context_summary}")

    return "\n\n".join(parts)
