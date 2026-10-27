#!/usr/bin/env python3
"""Export the event log as a JSONL action dataset — no IP/cookie/fingerprint.

One line per betting action, with hand context and (for LLM seats) full
provenance: model_id, prompt_version, reasoning, cost, latency. Session ids
are hashed: the raw id doubles as the browser cookie for human sessions.
A hand id is <session hash>:<table>:<hand_no>, the table counted from 1 within
the session: every table restarts hand_no. Every row carries the seat's
position, hole cards and stack at the start of the hand (stack_bb). 6-max
logs before the stack reset carried stacks between hands without logging
them; there the stack is rebuilt from the table's previous hands.
Hands that fail a check (placed on a table by guess, no single hand_end,
a seat that isn't at the table, format or engine version changing mid-hand,
the opponent's moves not logged: Slumbot plays on its own server, a 6-max
stack that can't be rebuilt) are left out and counted on stderr.

Usage:
  .venv/bin/python scripts/export_dataset.py --session-type bench --out bench.jsonl
  .venv/bin/python scripts/export_dataset.py --session-type human --since 2026-09-01
Sessions tagged internal in ops.db are left out unless --include-internal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from aipoker.engine import BB, POSITIONS  # noqa: E402
from aipoker.events import TableSplit, actor, lineup  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"
BOARD_AT = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
START = 100 * BB   # every table's stacks, and bench's every hand


def sid_hash(sid: str) -> str:
    return hashlib.sha256(sid.encode()).hexdigest()[:12]


def key(seat: dict) -> str:
    return seat.get("bot_key") or "hero"


def seats_of(start: dict) -> dict[str, dict]:
    """Seat key -> position and hole cards, from the hand_start record."""
    seats, hs = start.get("seats"), start.get("hero_seat")
    if seats and "bench_pair" in start:   # bench: the seat index is the position
        return {key(s): {"position": POSITIONS[2][s["seat"]], "cards": s.get("cards")}
                for s in seats}
    if seats:   # 6-max: physical player p sits at (p + hero_seat) % 6
        six = hs is not None and len(seats) == 6
        return {key(s): {"position": POSITIONS[6][(p + hs) % 6] if six else None,
                         "cards": s.get("cards")} for p, s in enumerate(seats)}
    hu = hs in (0, 1)
    out = {"hero": {"position": POSITIONS[2][hs] if hu else None,
                    "cards": start.get("hero_cards")}}
    if start.get("bot_key"):
        out[start["bot_key"]] = {"position": POSITIONS[2][1 - hs] if hu else None,
                                 "cards": start.get("bot_cards")}
    return out


def carry(prev: dict | None, hand_no: int, start: dict) -> list[int] | None:
    """6-max chips per physical player at this hand's start, rebuilt from the
    table's previous hand: the old engine kept every stack and topped up only
    under one big blind. None when the chain is broken."""
    seats = start.get("seats") or []
    if prev is None:
        return [START] * len(seats) if hand_no == 1 else None
    if (prev["stacks"] is None or prev["ends"] != 1 or hand_no != prev["hand_no"] + 1
            or prev["keys"] != [key(s) for s in seats]):
        return None
    return [START if s < BB else s for s in prev["stacks"]]


def settle(chain: dict, hand_no: int, end: dict) -> None:
    """Apply a 6-max hand's results to the carried stacks."""
    chain["ends"] += 1
    res = end.get("seat_results") or []
    if (chain["stacks"] is None or chain["ends"] != 1 or hand_no != chain["hand_no"]
            or [r.get("bot_key") or "hero" for r in res] != chain["keys"]):
        chain["stacks"] = None
        return
    chain["stacks"] = [s + round(r["payoff_bb"] * BB) for s, r in zip(chain["stacks"], res)]


def stacks_of(start: dict, carried: list[int] | None) -> dict[str, int] | None:
    """Seat key -> chips at the start of the hand, or None when unknown."""
    seats = start.get("seats")
    if seats and all("stack" in s for s in seats):
        return {key(s): s["stack"] for s in seats}
    if "bench_pair" in start:   # bench deals every hand at 100bb
        return {key(s): START for s in seats or []}
    if seats:
        return None if carried is None else dict(zip(map(key, seats), carried))
    st = start.get("stacks")
    if not st:
        return None
    out = {"hero": st["hero"]}
    if start.get("bot_key"):
        out[start["bot_key"]] = st["bot"]
    return out


def flaw(hand: dict) -> str | None:
    """Why a hand can't go out as one hand, or None."""
    start, ends = hand["start"], hand["ends"]
    if hand["unsure"]:
        return "table_unsure"
    if len(ends) != 1:
        return "hand_end_count"
    if "api" in start:
        return "opponent_unlogged"
    if hand["stacks"] is None:
        return "stack_unknown"
    end = ends[0]
    seats = start.get("seats")
    actors = {actor(a) for a in hand["actions"]}
    if seats:
        size = 6 if str(start.get("format", "")).startswith("6max") else 2
        if len(seats) > size or not actors <= lineup(seats):
            return "seats"
    elif len(actors) > 2:
        return "seats"
    for k in ("format", "engine_version"):
        if start.get(k) and end.get(k) and start[k] != end[k]:
            return k
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default=None, help="ISO date (UTC), e.g. 2026-09-01")
    ap.add_argument("--session-type", default="bench", choices=["bench", "human"])
    ap.add_argument("--out", default="-", help="output path, '-' = stdout")
    ap.add_argument("--db", default=str(DATA / "events.db"))
    ap.add_argument("--ops-db", default=str(DATA / "ops.db"))
    ap.add_argument("--include-internal", action="store_true",
                    help="keep sessions tagged internal in ops.db (debugging only)")
    args = ap.parse_args()

    # our own traffic: a session can be tagged internal after its hands were
    # logged as human, so the hand's session_type alone is not enough
    internal: set[str] = set()
    if not args.include_internal and Path(args.ops_db).exists():
        ops = sqlite3.connect(f"file:{args.ops_db}?mode=ro", uri=True)
        internal = {sid for (sid,) in ops.execute(
            "SELECT session_id FROM sessions WHERE internal=1")}

    since_ts = 0.0
    if args.since:
        since_ts = datetime.fromisoformat(args.since).replace(
            tzinfo=timezone.utc).timestamp()

    db = sqlite3.connect(args.db)
    cols = {r[1] for r in db.execute("PRAGMA table_info(events)")}
    tid_col = "table_id" if "table_id" in cols else "NULL"
    # insertion order within a session: hand_no and seq restart on every table
    cur = db.execute(
        f"SELECT ts, session_id, hand_no, seq, type, payload, {tid_col} FROM events "
        "WHERE ts >= ? ORDER BY session_id, id", (since_ts,))

    out = sys.stdout if args.out == "-" else open(args.out, "w")
    n = hands_out = 0
    dropped: Counter[str] = Counter()
    done: list[dict] = []   # this session's finished hands, written in start order

    def flush(hand: dict | None) -> None:
        if hand is None:
            return
        why = flaw(hand)
        if why:
            dropped[why] += 1
        else:
            done.append(hand)

    def write_session() -> None:
        for hand in sorted(done, key=lambda h: h["order"]):
            write(hand)
        done.clear()

    def write(hand: dict) -> None:
        nonlocal n, hands_out
        hands_out += 1
        start, end = hand["start"], hand["ends"][0]
        board = end.get("board", [])
        hu_bot = None if start.get("seats") else (start.get("bot_key") or end.get("bot_key"))
        payoff = {(r.get("bot_key") or "hero"): r.get("payoff_bb")
                  for r in end.get("seat_results", [])}
        if not payoff and end.get("payoff_bb") is not None:   # HU: hero's result, zero-sum
            payoff = {"hero": end["payoff_bb"]}
            if hu_bot:
                payoff[hu_bot] = -end["payoff_bb"]
        info, stacks = seats_of(start), hand["stacks"]
        for a in hand["actions"]:
            llm = a.get("llm") or {}
            seat = a.get("bot_key") or a.get("who")
            if seat == "bot" and hu_bot:
                seat = hu_bot
            at = info.get(seat, {})
            row = {
                "hand": f"{sid_hash(hand['sid'])}:{hand['table']}:{hand['hand_no']}",
                "session_type": hand["stype"],
                "format": end.get("format") or start.get("format"),
                "engine_version": start.get("engine_version"),
                "seat": seat,
                "position": at.get("position"),
                "hole_cards": at.get("cards"),
                "stack_bb": stacks[seat] / BB if seat in stacks else None,
                "street": a.get("street"),
                "board": board[:BOARD_AT.get(a.get("street"), 0)],
                "action": a.get("kind"),
                "amount": a.get("amount"),
                "model_id": llm.get("model_id"),
                "prompt_version": llm.get("prompt_version"),
                "reasoning": llm.get("reason"),
                "legal_actions": llm.get("legal"),
                "outcome": llm.get("outcome"),
                "cost_usd": llm.get("cost_usd"),
                "latency_ms": llm.get("latency_ms"),
                "showdown": end.get("showdown"),
                "payoff_bb": payoff.get(seat),
            }
            out.write(json.dumps({k: v for k, v in row.items() if v is not None},
                                 ensure_ascii=False) + "\n")
            n += 1

    split, split_sid = TableSplit(), None
    hands: dict[int, dict | None] = {}   # table number -> its open hand
    chains: dict[int, dict] = {}         # 6-max table number -> its carried stacks
    for order, (ts, sid, hand_no, seq, type_, raw, tid) in enumerate(cur):
        p = json.loads(raw)
        if sid != split_sid:
            for h in hands.values():
                flush(h)
            write_session()
            split, split_sid, hands, chains = TableSplit(), sid, {}, {}
        tn, unsure = split.place(seq, hand_no, type_, p, tid, ts)
        for t in unsure:
            if hands.get(t) is not None:
                hands[t]["unsure"] = True
            if t in chains:
                chains[t]["stacks"] = None
        if type_ == "hand_start":
            flush(hands.get(tn))
            carried = None
            if p.get("seats") and "bench_pair" not in p:
                carried = None if tn in unsure else carry(chains.get(tn), hand_no, p)
                chains[tn] = {"hand_no": hand_no, "stacks": carried, "ends": 0,
                              "keys": [key(s) for s in p["seats"]]}
            stype = p.get("session_type") or "human"
            keep = stype == args.session_type and sid not in internal
            hands[tn] = {"order": order, "sid": sid, "table": tn, "hand_no": hand_no, "stype": stype,
                         "start": p, "actions": [], "ends": [],
                         "stacks": stacks_of(p, carried),
                         "unsure": tn in unsure} if keep else None
            continue
        if type_ == "hand_end" and tn in chains:
            settle(chains[tn], hand_no, p)
        hand = hands.get(tn)
        if hand is None or type_ not in ("action", "hand_end"):
            continue
        if hand_no != hand["hand_no"]:
            hand["unsure"] = True
        elif type_ == "action":
            hand["actions"].append(p)
        else:
            hand["ends"].append(p)
    for h in hands.values():
        flush(h)
    write_session()
    if out is not sys.stdout:
        out.close()
    print(f"wrote {n} action rows, {hands_out} hands to {args.out}; "
          f"left out {sum(dropped.values())} hands {dict(dropped)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
