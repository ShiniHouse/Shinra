from typing import Any, Dict, List


class ConversationMemory:
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []

    def add_user_message(self, text: str) -> None:
        self.history.append({"role": "user", "content": text})
        self._trim()

    def add_assistant_message(self, text: str) -> None:
        self.history.append({"role": "assistant", "content": text})
        self._trim()

    def add_tool_interaction(self, tool_name: str, tool_args: Dict[str, Any], tool_result: Any) -> None:
        # Registra l'azione eseguita per mantenere il filo logico
        pass

    def get_messages(self) -> List[Dict[str, str]]:
        return list(self.history)

    def clear(self) -> None:
        self.history.clear()

    def _trim(self) -> None:
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-self.max_history * 2 :]


# Istanza singleton per la sessione principale
memory = ConversationMemory(max_history=10)
