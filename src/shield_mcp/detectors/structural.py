import math
import re
import binascii

class StructuralDetector:
    def __init__(self):
        # Thresholds
        self.entropy_threshold = 5.2 # Tuned slightly higher to avoid false positives on complex text
        self.base64_pattern = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
        self.hex_pattern = re.compile(r"^[0-9a-fA-F]+$")

    def calculate_entropy(self, text: str) -> float:
        if not text:
            return 0.0
        prob = [float(text.count(c)) / len(text) for c in dict.fromkeys(list(text))]
        entropy = -sum(p * math.log(p) / math.log(2.0) for p in prob)
        return entropy

    def check(self, prompt: str):
        """
        Returns: (is_injection, risk_score, category)
        """
        # Check 1: Base64/Hex (Specific checks first)
        # Look for suspicious long words
        words = prompt.split()
        for word in words:
            if len(word) > 30: # Long contiguous string
                if self.hex_pattern.match(word):
                    return True, 1.0, "Hex Encoding"

                if self.base64_pattern.match(word):
                    # Try to decode to see if it's valid
                    try:
                        # Add padding if missing just in case, though regex handles standard
                        missing_padding = len(word) % 4
                        if missing_padding:
                            word += '=' * (4 - missing_padding)
                        binascii.a2b_base64(word)
                        return True, 1.0, "Base64 Obfuscation"
                    except binascii.Error:
                        pass

        # Check 2: High Entropy
        if len(prompt) > 16:
            entropy = self.calculate_entropy(prompt)
            if entropy > self.entropy_threshold:
                return True, min(entropy / 8.0, 1.0), "High Entropy/Obfuscation"

        return False, 0.0, None
