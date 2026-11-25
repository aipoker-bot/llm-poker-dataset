#!/usr/bin/env python3
"""Made-hand claim detector for aipoker.bot LLM decision logs.

Flags rows where a model's written `reasoning` claims a stronger made hand for
itself than it actually holds on that street (for example saying "my set" or
"top two pair" while holding a single pair or ace-high).

Precision comes before recall: soft/draw language ("flush draw", "hoping to
spike a set"), negations ("no pair", "trips? wait, just a pair"), board threats
("flush-completing river") and opponent reads ("smells like a boat") are
filtered out clause by clause before ranking.

Runs with the Python 3 standard library only:

    python3 scripts/hallucination_detector.py data/human.jsonl
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

RANKS = "23456789TJQKA"

# Ordered weakest -> strongest; claimed_rank > actual_rank == hallucination.
CATS = [
    "pair",
    "two pair",
    "three of a kind",
    "straight",
    "flush",
    "full house",
    "four of a kind",
    "straight flush",
    "royal flush",
]

CLAIM_RX = {
    "royal flush": re.compile(r"royal flush", re.I),
    "straight flush": re.compile(r"straight flush(?!es)", re.I),
    "four of a kind": re.compile(
        r"four of a kind|quads|four (?:aces|kings|queens|jacks|tens|nines|eights|sevens|sixes|fives|fours|threes|deuces|twos)",
        re.I,
    ),
    "full house": re.compile(
        r"full house(?!s\b)|(?<!rock the )(?<!rocks the )(?<!rocked the )(?<!rocking the )\bboat\b(?!-|\s+(?:goes|bait|anchor|rock)\b)"
        r"|\b(?:aces|kings|queens|jacks|tens|nines|eights|sevens|sixes|fives|fours|threes|deuces|twos) full\b"
        r"(?! of (?!(?:aces|kings|queens|jacks|tens|nines|eights|sevens|sixes|fives|fours|threes|deuces|twos)\b))",
        re.I,
    ),
    "flush": re.compile(
        r"(?<!straight )(?<!royal )(?<!two[ -])(?<!three[ -])(?<!four[ -])(?<!\b[234][ -])\bflush\b",
        re.I,
    ),
    "straight": re.compile(
        r"(?<!\w)(?<!play )(?<!plays )(?<!played )(?<!playing )straight(?! flush)(?!s\b)"
        r"(?![ -]?(?:into|in\b|to\b|up\b|away|forward|out\b|off\b|back\b|down\b|through\b|ahead\b|for\s+the\s+(?:muck|door|exit|bin|trash)\b))",
        re.I,
    ),
    "three of a kind": re.compile(
        r"three of a kind|\btrips\b|\btrip\b(?!\s+(?:for|to)\b)"
        r"|\btripped (?:aces|kings|queens|jacks|tens|nines|eights|sevens|sixes|fives|fours|threes|deuces|twos)"
        r"|\b(?:a|my|the|our|flopped|flop|turned|rivered|top|bottom|middle|small|big)\s+set\b(?![ -]?(?:min|dream|up\b|value\b|ish\b))|\bset of\b",
        re.I,
    ),
    "two pair": re.compile(r"two pairs?\b(?!\s+in\s+(?:my|our)\s+hand\b)", re.I),
    "pair": re.compile(
        r"(?<!two )(?<!suited )(?<!suited-)\bpair\b(?!\s+of\s+(?:[\w-]+\s+)?cards\b)",
        re.I,
    ),
}

SOFT_RX = re.compile(
    r"draw|\bif\b|lands|\bhits?\b|\bspik(?:e|ing)\b|hoping|hope|need|miss|chance|potential|scare|threat|danger|possib"
    r"|\brisks?\b|\bworr(?:y|ies|ied|ying)\b|\bchas(?:e|es|ed|er|ers|ing)\b|\baim(?:s|ed|ing)?\s+(?:for|at)\b|\bshot at\b"
    r"|\bfish(?:es|ed|ing)?\s+for\b|\bgambl(?:e|es|ed|ing)\s+for\b|\bplay(?:s|ed|ing)?\s+for\s+an?\b"
    r"|board|gutshot|backdoor|\bouts?\b|mining|\bmine\b|hunt|flop a|flopping|turn a|river a"
    r"|\bbluff(?:ing|s)?\s+(?:a|an|the|with)\b|overcard|oesd|open-ended|open ended|equity|speculative|try to|could|might|\bmay\b"
    r"|\bto[ -]a\b|\bto the\b|dry|texture|blocker|represent|\breps?\b|\brepp(?:ing|ed)\b|nut\b|nutted|\bfill(?:ing)?\s+(?:an?|the|my|our)\b",
    re.I,
)

OTHER_RX = re.compile(
    r"\b(?:smell(?:s|ing)? (?:like|of)|plays? like|scream(?:s|ing)?|suggest(?:s|ed|ing)?|suspect(?:s|ed|ing)?|he|she|they|him|his|her|their|them"
    r"|villain|opponent|slumbot|someone|anyone|a (?:king|queen|jack|ten|nine|eight|seven|six|five|four|three|deuce|ace|\w+x?) has|range|likely|probably"
    r"|respect(?:s|ed|ing)?|wary of|isolat(?:e|es|ed|ing)\s+(?:the|a|an)"
    r"|think(?:s|ing)?\s+(?!i\b|i['’]|we\b|my\b)\w+\s+(?:caught|has|holds|made|hit|flopped|turned|rivered)"
    r"|crushed by|beat(?:en)? by|(?:dominat(?:es|ing)|beats|beating|crush(?:es|ing)) (?:me|us|my|our)\b|los(?:e|es|ing) to|against|behind"
    r"|(?:run(?:s|ning)?|jam(?:s|ming|med)?|shov(?:e|es|ing|ed)|bet(?:s|ting)?) into|ahead of|or better)\b",
    re.I,
)

NEG_BEFORE_RX = re.compile(
    r"(?:\bno\b|\bnot\b|\bwithout\b|n't|\bmissed\b|\bless\b|\bzero\b|\bnon-?|\black(?:s|ing)?\b)[\w\s'-]{0,18}$",
    re.I,
)
NEG_AFTER_RX = re.compile(
    r"^(?:-?ish\b)?[\s,.?!…-]*(?:no\b|not\b|nope|wait|er\b|erm\b|uh\b|um\b|actually|(?:just\s+)?kidding\b|jk\b|scratch that|correction|less\b|(?:i\s+)?doubt\b"
    r"|never\s+(?:arrived|came|got there|hit|showed|filled|materiali[sz]ed))",
    re.I,
)
WELL_JUST_AFTER_RX = re.compile(r"^[\s,]*well,?\s+(?:just|only|really)\b", re.I)
BOARD_AFTER_RX = re.compile(
    r"^(?:\s+(?:and|or|&)\s+[\w-]+(?:\s+house)?)?(?:[\s-]+(?:heavy|laden|rich|completing))?[\s-]+(?:board|texture|runout|flop|turn|river|cards?|(?:re)?draws|outs|threats?|risks?|combos?|possible|possibilities)\b"
    r"|^(?:\s+(?:and|or|&)\s+[\w-]+)?\s+out there\b"
    r"|^(?:\s+(?:and|or|&)\s+[\w-]+)?\s+all over\s+(?:the|this|that)\s+board\b"
    r"|^-(?:heavy|laden|rich)\b"
    r"|^[^,.;!?]{0,40}?\b(?:lurk|lurks|lurking|loom|looms|looming)\b",
    re.I,
)
SOFT_PAIR_BEFORE_RX = re.compile(r"\b(?:potential|possible)\s+[\w-]+\s+(?:and|or|&|/)\s+$", re.I)
DUAL_DRAW_AFTER_RX = re.compile(r"^\s+(?:and|or|&|/)\s+(?:straight|flush)\s+draw\b", re.I)
BOARD_EVENT_BEFORE_RX = re.compile(
    r"(?<!my )(?<!our )\b(?:river|turn|flop|card|board|ace|king|queen|jack|ten|nine|eight|seven|six|five|four|three|deuce|two)\s+"
    r"(?:just\s+)?(?:filled|fills|completed|completes|brought|brings|put|puts)\s+(?:(?:a|the|that|this)\s+)?$",
    re.I,
)
BOARD_EVENT_AFTER_RX = re.compile(
    r"^\s+(?:just\s+|now\s+)?(?:got there|gets there|came in|comes in|arrived|arrives|completed|completes)\b",
    re.I,
)
BOARD_EVENT_PAIR_AFTER_RX = re.compile(
    r"^\s+(?:and|or|&)\s+[\w-]+\s+(?:both\s+|all\s+)?(?:just\s+|now\s+)?(?:got there|came in|arrived|completed)\b",
    re.I,
)
_THE_BEFORE_RX = re.compile(
    r"\b(?:the|a)\s+(?:\w+-high\s+)?$|^\s*(?:(?:but|and|so|yet|now)\s+)?(?:\w+-high\s+)?$",
    re.I,
)
BOARD_HOLDS_BEFORE_RX = re.compile(
    r"\bboard(?:\s+texture)?\s+(?:(?:is|looks|feels|seems)\s+(?:(?:very|really|super|so|too|pretty|quite)\s+)?[\w-]+\s+)?"
    r"(?:with|showing)\s+(?:an?\s+|the\s+)?$",
    re.I,
)
CARD_GIVES_BEFORE_RX = re.compile(
    r"\b(?:an?|any)\s+(?:ace|king|queen|jack|ten|nine|eight|seven|six|five|four|three|deuce|two|[2-9tjqka])"
    r"(?:\s+or\s+(?:an?\s+)?(?:ace|king|queen|jack|ten|nine|eight|seven|six|five|four|three|deuce|two|[2-9tjqka]))*\s+(?:(?:still|also)\s+)?"
    r"(?:gives|makes|completes|would give|would make)\s+(?:(?:me|us)\s+(?:an?\s+|the\s+)?|(?:my|our)\s+)$",
    re.I,
)
OTHER_WITH_BEFORE_RX = re.compile(
    r"\b(?:human|villain|opponent)(?:[’']s)?\s+[\w\s-]{0,25}?\bwith\s+[\w\s-]{0,20}$",
    re.I,
)
OTHER_PRON_WITH_BEFORE_RX = re.compile(
    r"\b(?:they|them|he|she|him)\b(?:(?!\b(?:i|me|my|we|us|our)\b)[\w\s'-]){0,25}?\bwith\s+(?!(?:my|our)\b)[\w\s-]{0,20}$",
    re.I,
)
THATS_BEFORE_RX = re.compile(r"\bthat(?:['’]s|\s+is)\s+an?\s+(?:[\w-]+\s+)?$", re.I)
SUIT_FLUSH_BEFORE_RX = re.compile(r"\bthe\s+(?:clubs?|spades?|hearts?|diamonds?)\s+$", re.I)
LIVE_AFTER_RX = re.compile(r"^\s+(?:is|are)\s+(?:still\s+)?live\b", re.I)
THAT_STREET_BEFORE_RX = re.compile(r"\bthat\s+(?:river|turn|flop)\s+$", re.I)
SCARY_AFTER_RX = re.compile(
    r"^\s+(?:is|are|looks?|seems?|feels?)\s+(?:(?:very|really|super|so|too|pretty|quite)\s+)?scary\b(?![ -]+(?:strong|good|big))",
    re.I,
)
STARING_AFTER_RX = re.compile(
    r"^\s+(?:is|are)\s+(?:just\s+)?star(?:ing|es)\s+(?:right\s+)?at\s+(?:me|us)\b",
    re.I,
)
UNCONNECTED_BEFORE_RX = re.compile(r"\b(?:(?:un|dis)connected|suited)[\s-]+(?:[\w-]+\s+)?$", re.I)
WHAT_DOES_WITH_BEFORE_RX = re.compile(
    r"\bwhat\s+(?!i\b|we\b)[\w-]+\s+(?:does|do|did|will\s+do)\s+with\s+(?:(?:the|a|an|that|this|his|her|their)\s+)?$",
    re.I,
)
BLOCKS_BEFORE_RX = re.compile(
    r"\bblock(?:s|ed|ing)?\s+(?:(?:the|a|an|any|all|their|his|her)\s+)?(?:[\w-]+\s+)?$",
    re.I,
)
MY_BEFORE_RX = re.compile(r"\b(?:my|our)\s+(?:[\w-]+\s+)?$", re.I)
SEEK_BEFORE_RX = re.compile(
    r"\b(?:check|look|search|wait)(?:s|ed|ing)?\s+for\s+(?:(?:an?|any|some)\s+(?:[\w-]+\s+)?)?$",
    re.I,
)
WISH_AFTER_RX = re.compile(
    r"^\s+would\s+(?:be|have\s+been)\s+(?:(?:even|much|so)\s+)?(?:nicer|better|sweeter|ideal|preferable|lovely)\b",
    re.I,
)
FUTURE_AFTER_RX = re.compile(r"^\s+(?:incoming|in the making|on the way)\b", re.I)
GENERIC_AFTER_RX = re.compile(
    r"^(?:\s+[\w'-]+){0,2}\s+(?:often|sometimes|usually|rarely|tend)\b|^[\s-]+hands\b",
    re.I,
)

ACTUAL_MAP = [
    ("royal flush", "royal flush"),
    ("straight flush", "straight flush"),
    ("four of a kind", "four of a kind"),
    ("full house", "full house"),
    ("flush", "-high flush"),
    ("straight", "-high straight"),
    ("three of a kind", "three of a kind"),
    ("two pair", "two pair"),
    ("pair", "a pair of"),
]

HYPO_RX = re.compile(
    r"\b(?:can|could|might|may|would|often|sometimes|if|when|whenever|unless|hope|hoping|try|trying)\b",
    re.I,
)
_FULL_SPLIT = re.compile(r"(?<=[.;!])\s+")
_SENT_SPLIT = re.compile(
    r"(?<=[.;!])\s+|\s+[-—]\s+|[,:]\s+|\s+(?:with|plus|and|but|while|though|although|since|because|as)\s+",
    re.I,
)


def actual_rank(made: str | None) -> int:
    """Category index (0..8) from an engine `made` string, or -1 for high card."""
    if not made:
        return -1
    for cat, marker in ACTUAL_MAP:
        if marker in made:
            return CATS.index(cat)
    return -1


def _five_card_cat(cards5: tuple[str, ...]) -> int:
    rs = [c[0] for c in cards5]
    counts = sorted((rs.count(r) for r in set(rs)), reverse=True)
    flush = len({c[1] for c in cards5}) == 1
    idx = sorted(RANKS.index(r) for r in rs)
    wheel = idx == [0, 1, 2, 3, 12]
    straight = len(counts) == 5 and (idx[4] - idx[0] == 4 or wheel)
    if straight and flush:
        return 8 if (not wheel and idx[-1] == 12) else 7
    if counts[0] == 4:
        return 6
    if counts[0] == 3 and counts[1] == 2:
        return 5
    if flush:
        return 4
    if straight:
        return 3
    if counts[0] == 3:
        return 2
    if counts[0] == 2 and counts[1] == 2:
        return 1
    if counts[0] == 2:
        return 0
    return -1


def hand_rank_from_cards(hole_cards: list[str], board: list[str], fmt: str = "6max_nlhe") -> int:
    """Category index (-1..8) from `hole_cards` + `board` on any street."""
    if not hole_cards:
        return -1
    if not board:
        rs = [c[0] for c in hole_cards]
        return 0 if any(rs.count(r) >= 2 for r in set(rs)) else -1
    if fmt == "hu_plo":
        fives = (h2 + b3 for h2 in combinations(hole_cards, 2) for b3 in combinations(board, 3))
    else:
        cards = tuple(hole_cards) + tuple(board)
        fives = [cards] if len(cards) <= 5 else combinations(cards, 5)
    return max(_five_card_cat(tuple(f)) for f in fives)


def claimed_rank(reason: str | None) -> int:
    """Strongest made hand the reason claims for itself (0..8), or -1 if none."""
    if not reason:
        return -1
    best = -1
    text = re.sub(r"\.{2,}|…", " ", reason)
    for full in _FULL_SPLIT.split(text):
        pos = 0
        for clause in _SENT_SPLIT.split(full):
            at = full.find(clause, pos)
            pos = at + len(clause) if at >= 0 else pos
            if not clause or SOFT_RX.search(clause) or OTHER_RX.search(clause):
                continue
            for cat in reversed(CATS):
                m = CLAIM_RX[cat].search(clause)
                if not m:
                    continue
                if NEG_BEFORE_RX.search(clause[:m.start()]) or NEG_AFTER_RX.search(clause[m.end():]):
                    continue
                if at >= 0 and WELL_JUST_AFTER_RX.search(full[at + m.end():]):
                    continue
                if at >= 0 and BOARD_AFTER_RX.search(full[at + m.end():]):
                    continue
                if at >= 0 and cat in ("flush", "straight") and DUAL_DRAW_AFTER_RX.search(full[at + m.end():]):
                    continue
                if at >= 0 and SOFT_PAIR_BEFORE_RX.search(full[:at + m.start()]):
                    continue
                if cat == "pair" and UNCONNECTED_BEFORE_RX.search(clause[:m.start()]):
                    continue
                if at >= 0 and BOARD_HOLDS_BEFORE_RX.search(full[:at + m.start()]):
                    continue
                if at >= 0 and (
                    OTHER_WITH_BEFORE_RX.search(full[:at + m.start()])
                    or OTHER_PRON_WITH_BEFORE_RX.search(full[:at + m.start()])
                    or WHAT_DOES_WITH_BEFORE_RX.search(full[:at + m.start()])
                ):
                    continue
                if SUIT_FLUSH_BEFORE_RX.search(clause[:m.start()]) and LIVE_AFTER_RX.search(clause[m.end():]):
                    continue
                if (
                    GENERIC_AFTER_RX.search(clause[m.end():])
                    or FUTURE_AFTER_RX.search(clause[m.end():])
                    or (WISH_AFTER_RX.search(clause[m.end():]) and not MY_BEFORE_RX.search(clause[:m.start()]))
                    or CARD_GIVES_BEFORE_RX.search(clause[:m.start()])
                    or THAT_STREET_BEFORE_RX.search(clause[:m.start()])
                    or THATS_BEFORE_RX.search(clause[:m.start()])
                    or SEEK_BEFORE_RX.search(clause[:m.start()])
                    or BLOCKS_BEFORE_RX.search(clause[:m.start()])
                ):
                    continue
                if (
                    SCARY_AFTER_RX.search(clause[m.end():]) or STARING_AFTER_RX.search(clause[m.end():])
                ) and not MY_BEFORE_RX.search(clause[:m.start()]):
                    continue
                if BOARD_EVENT_BEFORE_RX.search(clause[:m.start()]) or (
                    _THE_BEFORE_RX.search(clause[:m.start()])
                    and (
                        BOARD_EVENT_AFTER_RX.search(clause[m.end():])
                        or (at >= 0 and BOARD_EVENT_PAIR_AFTER_RX.search(full[at + m.end():]))
                    )
                ):
                    continue
                if at >= 0 and HYPO_RX.search(full[:at + m.start()]):
                    continue
                best = max(best, CATS.index(cat))
                break
    return best


def is_hallucination(reason: str | None, made: str | None) -> bool:
    """True when `reason` claims a stronger made hand than `made`."""
    return claimed_rank(reason) > actual_rank(made)


def row_is_hallucination(row: dict) -> bool:
    """True when a dataset JSONL row's `reasoning` overclaims its cards + board."""
    reason = row.get("reasoning")
    if not reason:
        return False
    return claimed_rank(reason) > hand_rank_from_cards(
        row.get("hole_cards") or [],
        row.get("board") or [],
        row.get("format") or "6max_nlhe",
    )


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/human.jsonl")
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [scanned, flagged]
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            model = row.get("model_id")
            if not model or row.get("outcome") == "misfire":
                continue
            totals[model][0] += 1
            if row_is_hallucination(row):
                totals[model][1] += 1

    print(f"{'model_id':36s}  {'decisions':>9s}  {'flagged':>7s}  {'rate':>6s}")
    for model, (n, h) in sorted(totals.items(), key=lambda kv: (-kv[1][0], kv[0])):
        pct = (100.0 * h / n) if n else 0.0
        print(f"{model:36s}  {n:9d}  {h:7d}  {pct:5.1f}%")
    all_n = sum(v[0] for v in totals.values())
    all_h = sum(v[1] for v in totals.values())
    print(f"\nTotal: {all_h} flagged across {all_n} answered LLM decisions ({100.0 * all_h / max(1, all_n):.2f}%).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
