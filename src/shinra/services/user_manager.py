import logging
from typing import List, Optional

from pydantic import BaseModel

from shinra.infra.db import depositi

logger = logging.getLogger(__name__)


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


class UltimoAmministratore(Exception):
    """Sollevata quando si sta per restare senza nessuno che comanda.

    Cancellare o declassare l'ultimo amministratore chiude fuori tutti dalle
    impostazioni, dai profili e dai PIN — e non c'e' modo di rientrare se non
    mettendo le mani sul server. E' il genere di errore che si fa una volta
    sola, di sera, e si paga il giorno dopo.
    """


class UserManager:
    """L'anagrafica di casa.

    Dalla v0.2.0 legge e scrive nel database. I metodi e cio' che
    restituiscono sono quelli di prima: `UserProfile`, non dizionari, perche'
    le rotte, la sicurezza e l'agente lavorano su quello.
    """

    def get_users(self) -> List[UserProfile]:
        utenti: List[UserProfile] = []
        for riga in depositi.utenti.elenco():
            profilo = UserProfile(**riga)
            if not profilo.avatar_type or profilo.avatar_type in ["male_adult", "neutral", None]:
                profilo = auto_detect_avatar(profilo)
            utenti.append(profilo)
        return utenti

    def save_users(self, users: List[UserProfile]) -> None:
        """Riscrive l'intera anagrafica.

        Resta per compatibilita' con il codice che la usava quando i profili
        stavano in un file. Preferisci `upsert_user` e `imposta_pin`: toccano
        una riga sola e non cancellano cio' che ha appena fatto qualcun altro.
        """
        depositi.utenti.sostituisci_tutto([u.model_dump() for u in users])

    def get_user_by_id(self, user_id: str) -> Optional[UserProfile]:
        for u in self.get_users():
            if u.id.lower() == user_id.lower():
                return u
        return None

    def find_user_by_name(self, name_query: str) -> UserProfile:
        """Cerca l'utente dal nome detto a voce o scritto."""
        clean = name_query.strip().lower()
        for prefix in ["sono ", "mi chiamo ", "parli con ", "parla con ", "qui è ", "è "]:
            if clean.startswith(prefix):
                clean = clean[len(prefix) :].strip()

        for u in self.get_users():
            if u.name.lower() in clean or clean in u.name.lower():
                return u

        # Chi non e' registrato resta un ospite, e non viene salvato: la
        # famiglia si aggiunge dalle impostazioni, non pronunciando un nome.
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
        """Imposta o rimuove il PIN, sempre cifrato.

        Il PIN in chiaro non viene mai scritto: se un giorno il database
        finisse dove non deve, non regalerebbe l'accesso. Tocca la sola
        colonna del PIN — prima riscriveva tutta l'anagrafica, e cambiare il
        PIN mentre qualcun altro salvava un profilo poteva far sparire una
        delle due modifiche.
        """
        from shinra.api.sicurezza import cifra_pin  # import locale: evita un ciclo

        cifrato = cifra_pin(pin.strip()) if pin and pin.strip() else None
        return depositi.utenti.imposta_pin(user_id, cifrato)

    def amministratori(self) -> List[UserProfile]:
        return [u for u in self.get_users() if u.role == "admin"]

    def _sarebbe_l_ultimo(self, user_id: str) -> bool:
        amministratori = self.amministratori()
        return len(amministratori) == 1 and amministratori[0].id == user_id

    def upsert_user(self, user: UserProfile) -> None:
        esistente = depositi.utenti.per_id(user.id)
        if (
            esistente
            and esistente.get("role") == "admin"
            and user.role != "admin"
            and self._sarebbe_l_ultimo(user.id)
        ):
            raise UltimoAmministratore(
                "Non posso togliere i poteri all'ultimo amministratore: " "nomina prima qualcun altro."
            )
        dati = user.model_dump()
        if esistente and not dati.get("pin"):
            # L'interfaccia non rimanda il PIN quando salva un profilo: senza
            # questa riga, cambiare un nome lo cancellerebbe e chiuderebbe
            # fuori quella persona.
            dati["pin"] = esistente.get("pin")
        depositi.utenti.salva(dati)

    def delete_user(self, user_id: str) -> bool:
        if self._sarebbe_l_ultimo(user_id):
            raise UltimoAmministratore(
                "Non posso cancellare l'ultimo amministratore: nomina prima qualcun altro."
            )
        return depositi.utenti.cancella(user_id)


user_manager = UserManager()
