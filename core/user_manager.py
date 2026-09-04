import json
import logging
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
USERS_FILE = DATA_DIR / "users.json"


class UserProfile(BaseModel):
    id: str
    name: str
    role: str = "adult"  # admin, adult, teen, child, guest
    age_group: str = "adult"  # adult, teen, child
    gender: str = "unspecified"  # male, female, neutral, unspecified
    avatar_type: Optional[str] = None  # male_adult, female_adult, male_child, female_child, neutral, guest
    pin: Optional[str] = None
    preferred_news_categories: List[str] = ["generale"]
    restricted_topics: List[str] = []
    notes: Optional[str] = ""


GUEST_PROFILE = UserProfile(
    id="guest",
    name="Ospite",
    role="guest",
    age_group="adult",
    gender="neutral",
    avatar_type="guest",
    notes="Profilo ospite temporaneo con accesso base.",
)

FEMALE_HINTS = {
    "sonia",
    "daniela",
    "sofia",
    "giulia",
    "elena",
    "laura",
    "chiara",
    "francesca",
    "martina",
    "sara",
    "alice",
    "mamma",
    "moglie",
    "madre",
    "nonna",
    "zia",
    "ragazza",
    "bambina",
    "figlia",
}
MALE_HINTS = {
    "alessio",
    "maurizio",
    "thomas",
    "christian",
    "luca",
    "marco",
    "andrea",
    "francesco",
    "matteo",
    "papa",
    "papà",
    "padre",
    "marito",
    "nonno",
    "zio",
    "ragazzo",
    "bambino",
    "figlio",
}


def auto_detect_avatar(u: UserProfile) -> UserProfile:
    """Inferisce genere e avatar appropriato se non specificati o incoerenti."""
    name_l = u.name.lower()
    notes_l = (u.notes or "").lower()

    if u.role == "guest" or u.id == "guest":
        u.avatar_type = "guest"
        u.gender = "neutral"
        return u

    # Rilevamento femmina da nome o note (es. "Moglie", "Madre", "Sonia", "Daniela")
    is_female = any(w in name_l for w in FEMALE_HINTS) or any(
        w in notes_l for w in ["moglie", "madre", "mamma", "donna", "femmina", "figlia"]
    )
    # Rilevamento maschio da nome o note
    is_male = any(w in name_l for w in MALE_HINTS) or any(
        w in notes_l for w in ["marito", "padre", "papà", "papa", "uomo", "maschio", "figlio"]
    )

    if is_female:
        u.gender = "female"
        u.avatar_type = "female_child" if u.age_group == "child" else "female_adult"
    elif is_male:
        u.gender = "male"
        u.avatar_type = "male_child" if u.age_group == "child" else "male_adult"
    elif not u.avatar_type or u.avatar_type == "unspecified":
        if u.age_group == "child":
            u.avatar_type = (
                "male_child"
                if u.gender == "male"
                else ("female_child" if u.gender == "female" else "neutral")
            )
        else:
            u.avatar_type = (
                "female_adult"
                if u.gender == "female"
                else ("male_adult" if u.gender == "male" else "neutral")
            )
    return u


class UserManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not USERS_FILE.exists():
            self.save_users(
                [
                    UserProfile(
                        id="alessio",
                        name="Alessio",
                        role="admin",
                        age_group="adult",
                        gender="male",
                        avatar_type="male_adult",
                        preferred_news_categories=["economia", "tecnologia", "mondo"],
                        notes="Proprietario e amministratore principale di Shinra.",
                    )
                ]
            )

    def get_users(self) -> List[UserProfile]:
        try:
            if USERS_FILE.exists():
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    users = []
                    for u in data:
                        profile = UserProfile(**u)
                        if not profile.avatar_type or profile.avatar_type in ["male_adult", "neutral", None]:
                            # Esegui auto-detect se default per allineare subito nomi pre-esistenti
                            profile = auto_detect_avatar(profile)
                        users.append(profile)
                    return users
            return []
        except Exception as e:
            logger.error(f"Errore lettura users.json: {e}")
            return []

    def save_users(self, users: List[UserProfile]) -> None:
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump([u.model_dump() for u in users], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Errore salvataggio users.json: {e}")

    def get_user_by_id(self, user_id: str) -> Optional[UserProfile]:
        for u in self.get_users():
            if u.id.lower() == user_id.lower():
                return u
        return None

    def find_user_by_name(self, name_query: str) -> UserProfile:
        """Cerca l'utente in base al nome fornito a voce o per testo."""
        clean = name_query.strip().lower()
        # Rimuove preamboli tipici italiani come "sono", "mi chiamo", "parlo con", "è"
        for prefix in ["sono ", "mi chiamo ", "parli con ", "parla con ", "qui è ", "è "]:
            if clean.startswith(prefix):
                clean = clean[len(prefix) :].strip()

        users = self.get_users()
        for u in users:
            if u.name.lower() in clean or clean in u.name.lower():
                return u

        # Se non corrisponde a nessuno, crea o restituisce un profilo ospite con quel nome
        if clean:
            return UserProfile(
                id=f"guest_{clean}",
                name=clean.capitalize(),
                role="guest",
                age_group="adult",
                notes="Ospite non registrato.",
            )
        return GUEST_PROFILE

    def imposta_pin(self, user_id: str, pin: Optional[str]) -> bool:
        """Imposta o rimuove il PIN di un profilo, salvandolo sempre cifrato.

        Il PIN in chiaro non viene mai scritto su disco: se un giorno
        users.json finisse dove non deve, non regalerebbe l'accesso.
        """
        from server.sicurezza import cifra_pin  # import locale: evita un ciclo

        utenti = self.get_users()
        for i, u in enumerate(utenti):
            if u.id == user_id:
                utenti[i].pin = cifra_pin(pin.strip()) if pin and pin.strip() else None
                self.save_users(utenti)
                return True
        return False

    def upsert_user(self, user: UserProfile) -> None:
        users = self.get_users()
        updated = False
        for i, u in enumerate(users):
            if u.id == user.id:
                # L'interfaccia non rimanda il PIN quando salva un profilo:
                # senza questa riga, ogni modifica al nome lo cancellerebbe e
                # chiuderebbe fuori quella persona.
                if not user.pin:
                    user.pin = u.pin
                users[i] = user
                updated = True
                break
        if not updated:
            users.append(user)
        self.save_users(users)

    def delete_user(self, user_id: str) -> bool:
        users = self.get_users()
        filtered = [u for u in users if u.id != user_id]
        if len(filtered) < len(users):
            self.save_users(filtered)
            return True
        return False


user_manager = UserManager()
