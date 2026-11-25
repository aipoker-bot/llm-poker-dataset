# Checks on v0.2

Result: all checks passed, no failures.

The checks ran on `data/human.jsonl` (sha256 `dd11357b26a76595755a9dc904630e30f61d3ad92c8ac5b3ce2a2bb3593e66da`) before release, with a script that is not part of this repo. The file is the output of `scripts/export_dataset.py` on engine commit `53f3e77`: Slumbot hands left out, `position`, `hole_cards` and `stack_bb` on every row, 100 bb stacks at the start of every hand since `b882d04`. The site logged 18831 human hands over the period; 11905 are in the file and 6926 were dropped by the exporter (see "Left out" in the README).

| check | result | detail |
|---|---|---|
| row keys | OK | key set: action, amount, board, cost_usd, engine_version, format, hand, hole_cards, latency_ms, legal_actions, model_id, outcome, payoff_bb, position, prompt_version, reasoning, seat, session_type, showdown, stack_bb, street |
| every line is valid JSON | OK | 118206 rows, 0 broken |
| `session_type` is `human` | OK | other values: 0 |
| value scan: ipv4 | OK | matches: 0 |
| value scan: ipv6 | OK | matches: 0 |
| value scan: email | OK | matches: 0 |
| value scan: url | OK | matches: 0 |
| value scan: uuid | OK | matches: 0 |
| value scan: long hex string | OK | matches: 0 |
| value scan: cookie word | OK | matches: 0 |
| value scan: forbidden host | OK | matches: 0 |
| `hand` = `<sha256 of session[:12]>:<table>:<number>` | OK | violations: 0 |
| hand id is unique, rows of one hand are consecutive | OK | 11905 hands, 11905 blocks |
| one known `format` per hand | OK | violations: 0; 6max_nlhe 7765, hu_nlhe 3855, hu_plo 285 |
| one `engine_version` per hand | OK | violations: 0; hands without a value: 152 |
| seats in a hand do not exceed the table size | OK | violations: 0 |
| heads-up hand that reaches the flop has rows for both seats | OK | hands with only the human's rows: 0 |
| streets of a hand are in order | OK | violations: 0 |
| `board` is not longer than the street (no future cards leak) | OK | violations: 0; shorter than the street: 0 |
| `action` is one of fold, cc, raise | OK | fold 35903, raise 30508, cc 51795 |
| every raise has `amount` | OK | missing: 0 of 30508 |
| every row has `payoff_bb` | OK | missing: 0 of 118206; hero rows 30796, all with payoff |
| `payoff_bb` is the same on every row of a seat in a hand | OK | violations: 0 |
| payoffs sum to zero where every seat of the hand has rows | OK | 10672 such hands, 10672 sum to zero |
| every row has `position`, `hole_cards`, `stack_bb` | OK | rows without a value: 0 of 118206 |
| `position` is valid for the format, one per seat, not repeated between seats | OK | violations: 0 |
| `hole_cards`: 2 cards (4 in PLO), valid card format, same on every row of a seat | OK | wrong format or length: 0; changing within a hand: 0 |
| cards in a hand are unique (all seats' `hole_cards` plus `board`) | OK | hands with a repeated card: 0 |
| `stack_bb` is the same on every row of a seat in a hand | OK | violations: 0 |
| `stack_bb` > 0 and no seat loses more than its stack | OK | violations: 0 |
| hands on or after engine `b882d04` (stack reset): `stack_bb` = 100 for every seat | OK | 6517 hands, violations: 0 |
| exported + dropped = hands logged | OK | 11905 + 6926 = 18831 against 18831; hands in the file without recorded actions: 0 |
| `prompt_version` is set on LLM rows | OK | missing: 0 of 40932 |
| `prompt_version` >= 1.1.0 | OK | older: 0; versions: 1.2.1 = 40932 |
| no benchmark rows in the file | OK | benchmark rows: 0; all 792 benchmark hands counted as dropped (opponent moves not logged) |
| pandas opens the file | OK | 118206 rows, 21 columns |

Info, not a pass/fail check: in 4865 of 11905 hands some seat has `stack_bb` other than 100 (before `b882d04` stacks carried over between hands; the 6-max stacks were rebuilt from the table's earlier hands). The largest absolute `payoff_bb` is 2395.5; 2073 hands have an absolute result above 100.

Rows without `model_id`: 77274 = hero 30796 (the human), script 24577 (built-in bots), standin 21901 (a scripted bot played an LLM seat).
