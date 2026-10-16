import re
from typing import Tuple, Optional


# Severity tiers — used by future tooling to colour-code output.
# CRITICAL: obvious, high-confidence injection phrases
# HIGH:     strong injection indicators
# MEDIUM:   requires context to be malicious, but worth flagging


class HeuristicDetector:
    """
    Layer 1 detection — regex patterns against well-known jailbreak templates.

    Each pattern is anchored with word boundaries where appropriate to avoid
    false positives like "are you now ready to proceed" matching "you are now".

    Patterns are organised by category. Categories map to OWASP LLM Top 10
    (LLM01 Prompt Injection) where applicable.
    """

    # Ordered: most specific → most generic. First match wins.
    # Each tuple: (compiled_regex, category, severity)
    PATTERNS_RAW = [
        # ---- Instruction Override (OWASP LLM01) ----
        (r"\bignore\b.{0,40}\b(instructions?|directives?|rules?|prompts?|context|guidelines?|constraints?)\b",
         "Instruction Override", "CRITICAL"),
        (r"\b(disregard|forget|do not follow|don\u2019t follow|stop following|skip|bypass)\b.{0,40}\b(instruction|directive|rule|context|guideline)\b",
         "Instruction Override", "CRITICAL"),
        (r"\byour (new|real|true|actual|updated|original) instructions (are|say|follow|will be)\b",
         "Instruction Override", "CRITICAL"),
        (r"\boverride\b.{0,20}\b(prompt|instruction|directive|rule)\b",
         "Instruction Override", "CRITICAL"),

        # ---- System Override / Role Hijack ----
        # Only flag "system override" in imperative/immediate context — not as a
        # noun phrase like "the system override policy requires manager approval".
        (r"\b(system override|system update|system message)\b\s*[:!]",
         "System Override", "CRITICAL"),
        (r"\b(system override|system update|system message)\s+(is\s+)?(now|immediately|activated|engaged|in effect|hereby)\b",
         "System Override", "CRITICAL"),
        (r"\b<\|/?system\|>", "System Override", "CRITICAL"),
        (r"\b\[system\]|\[/system\]", "System Override", "HIGH"),
        # Developer mode — flag imperative/immediate context, but only when
        # the imperative is the attack itself (not a question or doc
        # explanation like "how do I enable developer mode on my Android
        # phone", which is the legitimate Android UI mode).
        # We use a separate "developer-mode-imperative-not-question"
        # pattern that's tighter: must NOT be preceded by "how" within
        # 24 chars, must be in imperative voice. Length-24 lookbehind
        # catches "how do I ", "how to ", "how can I ", "how does one ".
        (r"(?<!how do I )(?<!how to I )(?<!how can I )(?<!how does one )(?<!how would I )(?<!how could I )(?<!how should I )(?<!how is it )(?<!how are you )(?<!how did I )(?<!how do you )(?<!how do we )(?<!how do they )(?<!how do users )(?<!how to enable )(?<!how to activate )\b(enter|entering|enters?|enable|enables?|enabling|activate|activates?|activating|switch\s+to)\s+developer\s+mode\b",
         "Jailbreak", "CRITICAL"),
        (r"\bdeveloper\s+mode\b.{0,40}\b(jailbreak|unlock|hidden|secret|bypass|override|disable\s+(safety|filters?|restrictions?))\b",
         "Jailbreak", "CRITICAL"),
        # Maintenance mode — only flag imperative, not "kicks in at 3am" descriptions
        (r"\b(enter|entering|enable|enabling|activate|activating)\s+maintenance\s+mode\b",
         "Maintenance Mode", "CRITICAL"),
        (r"\bmaintenance\s+mode\s+(activated|engaged|now)\b",
         "Maintenance Mode", "HIGH"),

        # ---- Jailbreak / DAN family ----
        (r"\bDAN\b.{0,30}\b(do anything|jailbreak|enable|activate)\b",
         "DAN Mode", "CRITICAL"),
        (r"\bdo anything now\b", "DAN Mode", "CRITICAL"),
        (r"\bjailbreak(ed|ing)?\b", "Jailbreak", "HIGH"),
        (r"\bdude mode\b", "Jailbreak Variant", "HIGH"),
        (r"\bAIM\b.{0,30}\b(always intelligent|machiavellian)\b",
         "AIM Jailbreak", "CRITICAL"),
        (r"\b(?:anti-?GPT|stan|sam|KEVIN|BetterDAN)\b", "Jailbreak Persona", "HIGH"),

        # ---- Delimiter / Tag Hijacking ----
        # Tightened (2026-10): require the tag name to look like an
        # injection target (system/prompt/inst/etc.) — generic XML/HTML
        # tag names ("<user>", "<div>") are too broad and produce FPs on
        # any prompt that mentions template syntax. The catch-all
        # `</?[\w_-]+\s*>` was dropped.
        (r"</?(system(_prompt)?|inst|instructions?|context|prompt|im_start|im_end)\b",
         "Delimiter Hijacking", "CRITICAL"),
        (r"<\|/?(endoftext|im_start|im_end|system|user|assistant)\|?>",
         "Special Token Injection", "CRITICAL"),
        (r"```\s*(system|instructions?)\b", "Code Block Hijack", "HIGH"),
        (r"---\s*(system|new instructions)\b", "Frontmatter Hijack", "HIGH"),

        # ---- Persona Hijacking (fixed: word-boundary + context) ----
        (r"\byou are now\s+(a |an |my |the )?(?!ready\b|able\b|going\b|free\b|doing\b|reading\b|listening\b|able to\b|ready to\b)",
         "Persona Hijacking", "HIGH"),
        (r"\bpretend (to be|you are|you\u2019re)\b.{0,30}\b(hacker|attacker|criminal|jailbreak|uncensored|unfiltered|without restrictions|evil|immoral)\b",
         "Persona Hijacking", "CRITICAL"),
        (r"\bact as\b.{0,30}\b(developer|hacker|jailbreaker|uncensored|unfiltered)\b",
         "Persona Hijacking", "CRITICAL"),
        (r"\b(roleplay|role[\s-]play) as\b.{0,30}\b(hacker|attacker|jailbreak|uncensored|unfiltered)\b",
         "Persona Hijacking", "HIGH"),
        (r"\bfrom now on,?\s+you (will|are|shall|must)\b",
         "Persona Override", "HIGH"),

        # ---- Compliance / Legal / Authority Bypass ----
        # Tightened (2026-10): the phrase "required by law" / "required
        # by policy" alone is not an injection signal — it appears in
        # many legitimate prompts. The actual injection signal is the
        # imperative that follows ("required by law, therefore you must
        # bypass X"). Require an action verb to follow within ~30 chars.
        (r"\b(comply|cooperate) with my (request|instruction) immediately\b",
         "Authority Pressure", "HIGH"),
        (r"\b(required by (law|policy|compliance|our team))\b.{0,40}\b(you\s+must|you\s+should|you\s+will|therefore|immediately|bypass|override|ignore|disregard)\b",
         "Fake Authority", "HIGH"),
        (r"\bour (legal|compliance) team (requires|approved)\b.{0,40}\b(you\s+must|you\s+should|immediately|bypass|override|ignore|disregard)\b",
         "Fake Authority", "HIGH"),
        (r"\bthis is (an emergency|urgent|critical) and you must\b",
         "Urgency Pressure", "MEDIUM"),

        # ---- Output / Behaviour Exfiltration ----
        # Tightened (2026-10): require the request verb to be paired with
        # the *specific* exfil target ("system prompt", "hidden prompt",
        # "initial prompt", "secret prompt", "instructions") — not the
        # generic word "instructions" which appears in benign contexts
        # like "cooking instructions", "washing instructions", etc.
        # This eliminates FPs like "show me the cooking instructions"
        # while still catching "show me your system prompt".
        (r"\b(output|reveal|show|print|display|dump|leak|tell me|share)\b.{0,30}\b(system\s*prompt|hidden\s*prompt|initial\s*prompt|secret\s*prompt|hidden\s*rules?|system\s*instructions?|secret\s*instructions?)\b",
         "Prompt Exfiltration", "CRITICAL"),
        (r"\bwhat (is|are) your (system\s*prompt|hidden\s*rules?)\b",
         "Prompt Exfiltration", "CRITICAL"),
        (r"\brepeat (your|the) (system\s*prompt|initial\s*prompt|secret\s*instructions?) (verbatim|exactly)\b",
         "Prompt Exfiltration", "CRITICAL"),
        (r"\b(cat|less|head|tail|more|vi|vim|nano)\b\s+\.?/?~?/?\.?(ssh|id_rsa|aws/credentials|netrc|\.env)\b",
         "Secret Exfiltration", "CRITICAL"),
        (r"\b(show|output|reveal|dump|print|display)\b.{0,20}\b(ssh/id_rsa|id_rsa|aws/credentials|netrc|\.env)\b",
         "Secret Exfiltration", "CRITICAL"),
        (r"\bread\b\s+(\.?/?~?/)?\.?(ssh/id_rsa|id_rsa|aws/credentials|netrc|\.env)\b",
         "Secret Exfiltration", "CRITICAL"),
        (r"\bcurl\b.{0,30}\b(exfil|attacker|evil|webhook)\b",
         "Exfiltration Attempt", "CRITICAL"),
        (r"\bsend (it|the data|the file) to\b.{0,30}\b(http|attacker|evil)\b",
         "Exfiltration Attempt", "CRITICAL"),

        # ---- Indirect-injection markers (in retrieved docs / tool output) ----
        (r"\bIMPORTANT:?\s+(when|before|after)\s+(you\s+)?(summarizing|responding|replying|executing)\b",
         "Indirect Injection Marker", "HIGH"),
        (r"\b(compliance|security)\s+(policy|requirement):?\s+(execute|run|output|include)\b",
         "Indirect Injection Marker", "HIGH"),
        (r"\bdo not (mention|tell|reveal|show)\b.{0,30}\b(this|these|the)\s+instructions?\b",
         "Hidden Instruction", "CRITICAL"),
        (r"\b<!--\s*(SYSTEM|INSTRUCTION|OVERRIDE|IGNORE)\b",
         "Hidden HTML Instruction", "CRITICAL"),
        (r"\bfile:\s*(//|C:|[A-Z]:).*?\.(env|key|pem|p12)\b",
         "Secret File Reference", "HIGH"),

        # ---- Prompt-leak scaffolding (modern variants) ----
        (r"\btoken\s*smuggling\b", "Token Smuggling", "HIGH"),
        (r"\b(base64|hex|rot13|atob|btoa)\s*(decode|encode)\b.{0,30}\binstruction",
         "Encoded Instruction", "HIGH"),
        (r"\bin\s+your\s+(response|reply|answer).{0,30}\boutput\s+the\s+following\b",
         "Output Scaffolding", "MEDIUM"),
        (r"\bbefore\s+(answering|responding).{0,30}\bignore\b",
         "Preamble Hijack", "HIGH"),
    ]

    def __init__(self):
        self.compiled_patterns = [
            (re.compile(p, re.IGNORECASE | re.DOTALL), cat, sev)
            for p, cat, sev in self.PATTERNS_RAW
        ]

    def check(self, prompt: str) -> Tuple[bool, float, Optional[str]]:
        """
        Returns: (is_injection, risk_score, category)

        Risk score is mapped from severity:
            CRITICAL -> 1.0, HIGH -> 0.85, MEDIUM -> 0.65
        """
        for pattern, category, severity in self.compiled_patterns:
            if pattern.search(prompt):
                score = {"CRITICAL": 1.0, "HIGH": 0.85, "MEDIUM": 0.65}[severity]
                return True, score, category
        return False, 0.0, None

    def categories_matched(self, prompt: str) -> list:
        """Return all matching categories (for diagnostics / bench output)."""
        return [
            cat for pattern, cat, _sev in self.compiled_patterns
            if pattern.search(prompt)
        ]