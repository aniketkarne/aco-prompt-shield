import math
import re
import binascii
import base64


class StructuralDetector:
    """
    Layer 3 detection — base64 / hex / high-entropy payloads.

    Naive versions of this detector (raw regex on long words) produced
    severe false positives on benign content — MD5 / SHA / UUID /
    base64-encoded attachments / JWTs — because every long word of
    hex or base64 chars was flagged regardless of what it actually
    decoded to.

    The corrected policy: only flag a long token if, after decoding,
    the result actually looks like an injection prompt. We use a
    tight discrimination signal — the decoded text must contain at
    least one natural-language marker (a space and a lowercase ASCII
    letter). That separates obfuscated injection phrases ("Ignore all
    previous instructions") from arbitrary opaque data (hashes,
    identifiers, JSON tokens).
    """

    # Long words above this length get the hex / base64 decode check.
    # Below this, common words/string fragments stay safe.
    LONG_WORD_THRESHOLD = 30

    # Catches the canonical attack: a long token whose decoded form
    # contains a space and at least one lowercase ASCII letter.
    # - "Ignore all previous instructions"          -> True
    # - "disregard previous rules"                   -> True
    # - MD5 / SHA / UUID (decodes to binary garbage) -> False
    # - JWT body (decodes to JSON punctuation)       -> False
    # - "Hello World" (benign but rare in prompts)   -> True, but
    #   the heuristic layer would catch any real injection before we
    #   get here, and "Hello World" alone does not contain injection
    #   keywords — we additionally require the decoded text to contain
    #   at least one *common English word* from a deny-list of
    #   injection indicators.
    _INJECTION_KEYWORDS = (
        "ignore", "disregard", "forget", "override", "bypass",
        "instructions", "directive", "previous", "rules", "prompt",
        "system", "jailbreak", "developer mode", "previous instructions",
    )

    def __init__(self):
        # Tuned slightly higher to avoid false positives on complex text
        self.entropy_threshold = 5.2
        # Strict: only [A-Za-z0-9+/] and optional = padding (RFC 4648).
        self.base64_pattern = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
        # Strict: only [0-9a-fA-F].
        self.hex_pattern = re.compile(r"^[0-9a-fA-F]+$")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_entropy(self, text: str) -> float:
        if not text:
            return 0.0
        prob = [float(text.count(c)) / len(text) for c in dict.fromkeys(list(text))]
        entropy = -sum(p * math.log(p) / math.log(2.0) for p in prob)
        return entropy

    def check(self, prompt: str):
        """
        Returns: (is_injection, risk_score, category)

        Hex / base64 are now decode-aware: a long token is only flagged
        if its decoded form actually contains natural-language injection
        indicators. This eliminates false positives on MD5 / SHA / UUID /
        JWT / base64 attachments while preserving detection of the
        canonical obfuscated injection phrases.
        """
        # Check 1: Long words that decode to natural-language injection text
        words = prompt.split()
        for word in words:
            if len(word) <= self.LONG_WORD_THRESHOLD:
                continue

            # Try hex first (strict: even length, hex-only chars)
            if self.hex_pattern.match(word) and len(word) % 2 == 0:
                decoded = self._try_decode_hex(word)
                if decoded is not None and self._looks_like_injection(decoded):
                    return True, 1.0, "Hex Encoding"
                # Either not valid hex bytes, or decoded to garbage that
                # doesn't contain injection markers — skip this word.
                continue

            # Then try base64 (strict RFC 4648 alphabet)
            if self.base64_pattern.match(word):
                decoded = self._try_decode_base64(word)
                if decoded is not None and self._looks_like_injection(decoded):
                    return True, 1.0, "Base64 Obfuscation"
                continue

        # Check 2: High entropy across the whole prompt
        if len(prompt) > 16:
            entropy = self.calculate_entropy(prompt)
            if entropy > self.entropy_threshold:
                return True, min(entropy / 8.0, 1.0), "High Entropy/Obfuscation"

        return False, 0.0, None

    # ------------------------------------------------------------------
    # Decoding helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _try_decode_hex(word: str) -> str | None:
        """Decode a hex string. Returns None if the bytes are not valid UTF-8."""
        try:
            raw = binascii.unhexlify(word)
        except (binascii.Error, ValueError):
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None

    @staticmethod
    def _try_decode_base64(word: str) -> str | None:
        """Decode a base64 string. Returns None if invalid or non-UTF-8."""
        pad = "=" * (-len(word) % 4)
        try:
            raw = base64.b64decode(word + pad, validate=True)
        except (binascii.Error, ValueError):
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None

    @classmethod
    def _looks_like_injection(cls, decoded: str) -> bool:
        """
        Cheap discriminator: a real obfuscated injection phrase contains
        natural-language English words. Random data (hashes, UUIDs) and
        structured tokens (JWTs, JSON) do not.

        Required signals (all):
        - at least one ASCII space (multi-word phrase)
        - at least one lowercase ASCII letter
        - at least one keyword from the injection indicator list
        """
        if not decoded:
            return False
        if " " not in decoded:
            return False
        lower = decoded.lower()
        if not any(c.isascii() and c.islower() for c in lower):
            return False
        return any(keyword in lower for keyword in cls._INJECTION_KEYWORDS)
