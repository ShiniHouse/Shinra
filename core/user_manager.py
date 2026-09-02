import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
USERS_FILE = DATA_DIR / "users.json"

class UserProfile(BaseModel):
    id: str
    name: str
    role: str = "adult" # admin, adult, teen, child, guest
    age_group: str = "adult" # adult, teen, child
    gender: str = "male" # male, female, neutral, unspecified
    avatar_type: Optional[str] = "male_adult" # male_adult, female_adult, male_child, female_child, neutral, guest
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
    notes="Profilo ospite temporaneo con accesso base."
)

class UserManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not USERS_FILE.exists():
            self.save_users([
                UserProfile(
                    id="alessio",
                    name="Alessio",
                    role="admin",
                    age_group="adult",
                    preferred_news_categories=["economia", "tecnologia", "mondo"],
                    notes="Proprietario e amministratore principale di Shinra."
                )
            ])

    def get_users(self) -> List[UserProfile]:
        try:
            if USERS_FILE.exists():
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [UserProfile(**u) for u in data]
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
                clean = clean[len(prefix):].strip()

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
                notes="Ospite non registrato."
            )
        return GUEST_PROFILE

    def upsert_user(self, user: UserProfile) -> None:
        users = self.get_users()
        updated = False
        for i, u in enumerate(users):
            if u.id == user.id:
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
