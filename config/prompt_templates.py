import datetime
from typing import Optional
from config.settings import settings
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
    assistant_name = getattr(settings.assistant, "name", "Kyra") or "Kyra"
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
        f"Sei {assistant_name}, assistente domestico intelligente. Oggi è {now_str}. Città di riferimento: {default_city}.",
        persona,
        f"""REGOLE SUI TOOL (Usa sempre i tool per dati in tempo reale o azioni):
- METEO: Per qualsiasi domanda sul meteo o temperature, chiama SEMPRE il tool `get_weather` (default location: "{default_city}").
- DOMOTICA: Per accendere/spegnere/regolare luci o verificare lo stato di casa, chiama `control_device` o `get_home_status`.
- NOTIZIE: Per notizie del giorno o rassegna stampa, chiama `get_latest_news` o `search_web`.
- CULTURA & DEFINIZIONI: Per definizioni o concetti, chiama `search_wikipedia`.
Non dire mai che non puoi accedere a dati in tempo reale: invoca sempre il tool appropriato. Quando ricevi i dati dal tool, formula una risposta breve, chiara e naturale per l'utente in 1-2 frasi.""",
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
