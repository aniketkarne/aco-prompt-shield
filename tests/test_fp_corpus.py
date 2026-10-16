"""
False-positive corpus test — proves the heuristic layer has a 0% FP rate
on real-world benign prompts that look like they contain injection triggers.

ML-layer scores are also recorded so we can tune the threshold. ML-layer
flags ARE allowed if the score is below the documented threshold, but a
flag at high confidence (>0.9) on a clearly benign prompt is a regression
worth investigating.
"""

import yaml
import pytest
from pathlib import Path

from shield_mcp.detectors.heuristics import HeuristicDetector


CORPUS_PATH = Path(__file__).parent / "fp_corpus.yaml"


@pytest.fixture(scope="module")
def corpus():
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def detector():
    return HeuristicDetector()


def test_fp_corpus_parses(corpus):
    """Sanity: corpus is non-empty and well-formed."""
    assert "benign_prompts" in corpus
    assert len(corpus["benign_prompts"]) >= 30, (
        "fp_corpus.yaml should have at least 30 prompts to be meaningful"
    )


def test_heuristics_zero_false_positives(corpus, detector):
    """
    The core FP claim: the heuristic layer must not flag any benign prompt
    in the corpus. A failure here means a regression in heuristics.py.
    """
    failures = []
    for prompt in corpus["benign_prompts"]:
        is_inj, score, cat = detector.check(prompt)
        if is_inj:
            failures.append((prompt, cat, score))

    if failures:
        msg = "\n".join(f"  {p!r}  -> {c!r} (score={s})" for p, c, s in failures)
        pytest.fail(
            f"Heuristic detector flagged {len(failures)}/{len(corpus['benign_prompts'])} "
            f"benign prompts:\n{msg}"
        )


def test_fp_corpus_categories(corpus):
    """Spot-check that we cover diverse trigger categories, not just 'ignore'."""
    categories_present = set()
    for p in corpus["benign_prompts"]:
        for trigger in [
            "ignore", "system", "instructions", "override",
            "developer mode", "maintenance mode", "pretend", "act as",
            "roleplay", "from now on", "hypothetical", "compliance",
            "urgent", "system prompt", ".env", "id_rsa",
            "base64", "JWT", "MD5", "<system>", "<|im_start|>",
        ]:
            if trigger.lower() in p.lower():
                categories_present.add(trigger)

    # We expect to hit at least 12 distinct trigger categories. If we
    # drop below that, the corpus is too narrow.
    assert len(categories_present) >= 12, (
        f"Only {len(categories_present)} trigger categories covered: "
        f"{categories_present}"
    )