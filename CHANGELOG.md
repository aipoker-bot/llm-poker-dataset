# Changelog

Append-only. Newest release on top.

## v0.2

- Updated `data/human.jsonl`: 118206 rows, 11905 hands played by visitors across 53 language models, 2026-08-19 to 2026-11-25 (event-log snapshot 2026-11-25 17:21 UTC; adds 6507 hands and 61141 rows on the 100-bb engine since v0.1).
- Added `scripts/hallucination_detector.py` so made-hand claim checks can be reproduced directly on `data/human.jsonl`.

## v0.1

- Added `data/human.jsonl`: 57065 rows, 5398 hands played by visitors, 2026-08-19 to 2026-10-27 (event-log snapshot 2026-10-27 15:51 UTC).
- Left out hands against Slumbot and all benchmark hands (opponent moves are not logged).
