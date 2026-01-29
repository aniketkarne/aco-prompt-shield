import re
from typing import Tuple, Optional

class HeuristicDetector:
    def __init__(self):
        self.patterns = [
            (r"ignore all previous instructions", "Instruction Override"),
            (r"system override", "System Override"),
            (r"entering developer mode", "Jailbreak"),
            (r"<\/system_prompt>", "Delimiter Hijacking"),
            (r"you are now", "Persona Hijacking"),
            (r"do anything now", "DAN Mode"),
        ]
        self.compiled_patterns = [(re.compile(p, re.IGNORECASE), cat) for p, cat in self.patterns]

    def check(self, prompt: str) -> Tuple[bool, float, Optional[str]]:
        """
        Checks the prompt against heuristic patterns.
        Returns: (is_injection, risk_score, category)
        """
        for pattern, category in self.compiled_patterns:
            if pattern.search(prompt):
                return True, 1.0, category
        return False, 0.0, None
