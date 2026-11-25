# aipoker.bot hand log, v0.2

Every betting action from poker hands that people played on [aipoker.bot](https://aipoker.bot) against language models and classic scripted bots. One JSONL row per action. For the LLM seats each row carries the model id, the frozen prompt version, the model's own one-line reason, cost and latency.

- 118206 rows, 11905 hands, 458 sessions, three formats (6-max No-Limit Hold'em, heads-up No-Limit Hold'em, heads-up Pot-Limit Omaha).
- 40932 rows are decisions of 53 language models, all on prompt 1.2.1. The rest are the human (30796), scripted bots (24577) and scripted stand-ins that took over an LLM seat when its daily quota or the budget ran out (21901).
- Hands were logged from 2026-08-19 to 2026-11-25 (UTC). Rows carry no timestamps.
- License CC BY 4.0. Snapshot of the event log: 2026-11-25 17:21 UTC.

This is a log of people playing, not a tournament. Line-ups, formats and the number of hands per model are whatever the players got.

## Files

- `data/human.jsonl`: the dataset. sha256 `dd11357b26a76595755a9dc904630e30f61d3ad92c8ac5b3ce2a2bb3593e66da`.
- `scripts/export_dataset.py`: the exporter that wrote it. It reads the site's event log, so it is reference only and won't run on this file.
- `scripts/hallucination_detector.py`: standalone rule-based detector for "claimed a hand it didn't have". Uses only the Python standard library and runs directly on `data/human.jsonl`.
- `CHECKS.md`: the checks run on the file before release (privacy scan, hand ids, zero-sum payoffs, card uniqueness, row counts) and their results.
- `CITATION.cff`, `CHANGELOG.md`.

## Rows

| field | type | meaning |
|---|---|---|
| `hand` | string | `<sha256 of the session id, first 12 hex>:<table>:<hand number>`. The table is counted from 1 inside a session, because hand numbers restart on every table. Rows of one hand are consecutive. |
| `session_type` | string | `human` in v0.2: hands played by a visitor. |
| `format` | string | `6max_nlhe`, `hu_nlhe` or `hu_plo`. Blinds 1/2. |
| `engine_version` | string | Git commit of the game engine that dealt the hand. Missing for 152 hands. |
| `seat` | string | `hero` is the human. Any other value is a bot key: an LLM seat or a scripted bot. |
| `position` | string | 6-max: `UTG`, `HJ`, `CO`, `BTN`, `SB`, `BB`. Heads-up: `BTN/SB`, `BB`. |
| `hole_cards` | list | The seat's own cards at the start of the hand, like `["Ac", "5d"]`. Two cards, four in PLO. |
| `stack_bb` | number | The seat's stack at the start of the hand, in big blinds. See the stack note below. |
| `street` | string | `preflop`, `flop`, `turn`, `river`. |
| `board` | list | Community cards visible on that street. Later cards are not in the row. |
| `action` | string | `fold`, `cc` (check or call) or `raise`. |
| `amount` | integer | Raises only: the total "raise to" amount in chips, 1 big blind = 2 chips. |
| `model_id` | string | LLM rows only. The model that answered. |
| `prompt_version` | string | LLM rows only. Frozen prompt, always `1.2.1` in v0.2. |
| `reasoning` | string | LLM rows only. The model's written reason, verbatim, 20 words or fewer. It explains the answer; it is not a record of what the model computed. Empty on 139 rows. |
| `legal_actions` | list | LLM rows only. What the model was allowed to do: `fold`, `call`, `raise`. |
| `outcome` | string | LLM and stand-in rows. `ok`; `mapped` (illegal answer, played as the nearest legal action); `misfire` (no usable answer, the seat checked or folded); `standin` (a scripted bot played this LLM seat). |
| `cost_usd` | number | LLM rows only. Cost of the API call. Missing on 37 rows. |
| `latency_ms` | integer | LLM rows only. |
| `showdown` | boolean | The hand went to showdown. |
| `payoff_bb` | number | The seat's net result for the hand, in big blinds. The same on every row of that seat in the hand. |

Missing values are omitted from the row. A scripted stand-in row keeps the LLM's key in `seat` and has no `model_id`: group by `model_id`, not by `seat`.

Load it:

```python
import pandas as pd
df = pd.read_json("data/human.jsonl", lines=True)
llm = df[df.model_id.notna()]
```

## What is in it

| format | hands | rows |
|---|---:|---:|
| 6max_nlhe | 7765 | 96627 |
| hu_nlhe | 3855 | 20213 |
| hu_plo | 285 | 1366 |

3199 of the 11905 hands went to showdown. LLM rows by outcome: ok 40627, mapped 169, misfire 136.

Decisions per model. Eighteen models have 1000 or more decisions in this file; the rest rest on a few dozen to several hundred decisions.

<details>
<summary>53 models</summary>

| model_id | decisions | hands | 6max_nlhe | hu_nlhe | hu_plo |
|---|---:|---:|---:|---:|---:|
| qwen/qwen3.8-27b | 2240 | 896 | 2240 | 0 | 0 |
| openai/gpt-6-astra | 2127 | 981 | 776 | 1338 | 13 |
| mistralai/ministral-14b-2512 | 2101 | 781 | 2101 | 0 | 0 |
| z-ai/glm-4.7-flash | 1808 | 603 | 1808 | 0 | 0 |
| google/gemma-4-31b-it | 1760 | 748 | 1760 | 0 | 0 |
| x-ai/grok-4.7 | 1705 | 820 | 599 | 905 | 201 |
| openai/gpt-oss-20b | 1458 | 702 | 1458 | 0 | 0 |
| nvidia/nemotron-3.5-lightning | 1402 | 446 | 1402 | 0 | 0 |
| deepseek/deepseek-v4-flash | 1391 | 399 | 1384 | 7 | 0 |
| anthropic/claude-opus-5.5 | 1373 | 622 | 749 | 440 | 184 |
| z-ai/glm-5.3 | 1347 | 584 | 1335 | 12 | 0 |
| meta-llama/llama-3.1-8b-instruct | 1299 | 333 | 1299 | 0 | 0 |
| anthropic/claude-haiku-5.5 | 1253 | 482 | 1195 | 52 | 6 |
| minimax/minimax-m3 | 1196 | 562 | 1179 | 17 | 0 |
| openai/gpt-5.4-mini | 1152 | 346 | 1152 | 0 | 0 |
| qwen/qwen3.7-plus | 1043 | 547 | 1038 | 0 | 5 |
| qwen/qwen3.8-flash | 1042 | 529 | 1042 | 0 | 0 |
| z-ai/glm-5.3-flash | 1010 | 465 | 921 | 89 | 0 |
| mistralai/mistral-medium-3-5 | 965 | 531 | 950 | 15 | 0 |
| deepseek/deepseek-v4.1-flash | 872 | 369 | 850 | 22 | 0 |
| anthropic/claude-fable-5.1 | 828 | 466 | 799 | 29 | 0 |
| openai/gpt-6.1-sol | 816 | 521 | 750 | 66 | 0 |
| google/gemma-4-26b-a4b-it | 812 | 389 | 812 | 0 | 0 |
| deepseek/deepseek-v4-pro-0813 | 795 | 382 | 792 | 3 | 0 |
| anthropic/claude-sonnet-5.5 | 760 | 430 | 760 | 0 | 0 |
| google/gemini-3.1-pro-preview | 695 | 451 | 567 | 128 | 0 |
| openai/gpt-5.6-terra | 691 | 376 | 678 | 13 | 0 |
| x-ai/grok-4.6 | 637 | 284 | 164 | 427 | 46 |
| qwen/qwen3.8-max-0902 | 592 | 367 | 592 | 0 | 0 |
| ibm-granite/granite-4.2-8b | 588 | 580 | 588 | 0 | 0 |
| openai/gpt-6-luna | 565 | 309 | 565 | 0 | 0 |
| google/gemini-3.8-flash | 556 | 375 | 549 | 7 | 0 |
| mistralai/mistral-large-4-0 | 474 | 244 | 474 | 0 | 0 |
| anthropic/claude-haiku-4.5 | 466 | 224 | 464 | 2 | 0 |
| mistralai/mistral-small-2603 | 448 | 176 | 372 | 76 | 0 |
| moonshotai/kimi-k3 | 441 | 213 | 437 | 4 | 0 |
| tencent/hy4 | 317 | 139 | 317 | 0 | 0 |
| xiaomi/mimo-v2.6-pro | 300 | 114 | 300 | 0 | 0 |
| xiaomi/mimo-v2.6-flash | 266 | 113 | 266 | 0 | 0 |
| google/gemini-4-argon | 199 | 108 | 107 | 92 | 0 |
| google/gemini-4-carbon | 191 | 122 | 191 | 0 | 0 |
| openai/gpt-6.1-terra | 188 | 105 | 186 | 0 | 2 |
| openai/gpt-5.6-sol | 148 | 69 | 54 | 94 | 0 |
| meta/muse-wonder | 141 | 82 | 141 | 0 | 0 |
| anthropic/claude-sonnet-5 | 133 | 81 | 133 | 0 | 0 |
| openai/gpt-5.6-luna | 94 | 48 | 94 | 0 | 0 |
| moonshotai/kimi-k3.1-pro | 88 | 46 | 88 | 0 | 0 |
| google/gemini-4-hydrogen | 75 | 47 | 75 | 0 | 0 |
| google/gemini-3.7-flash | 61 | 41 | 61 | 0 | 0 |
| anthropic/claude-opus-5 | 12 | 5 | 11 | 1 | 0 |
| x-ai/grok-4.3 | 7 | 7 | 2 | 3 | 2 |
| mistralai/mistral-large-2512 | 3 | 3 | 3 | 0 | 0 |
| meta/muse-spark-1.3 | 1 | 1 | 1 | 0 | 0 |

</details>

## Left out

18831 hands were logged by the site over the same period; 6926 are not in the file.

- 6311 hands against Slumbot. Slumbot plays on its own server, so the log has the human's moves and not the opponent's. A hand without the opponent's moves is not a hand of this dataset.
- 792 benchmark hands (`session_type` bench, 9 sessions on 2026-09-14). All of them were against Slumbot, so v0.2 has no bench rows.
- 417 hands without exactly one end record, mostly hands abandoned midway.
- 35 hands that could not be placed on a table with certainty.
- 163 early 6-max hands whose starting stacks could not be rebuilt.

Also left out: the site's own test sessions, and anything that identifies a player. Session ids are hashed; the file has no IP, cookie, fingerprint, email or URL (`CHECKS.md` lists the scans).

## Limitations

- Stacks. Since 2026-10-27 (engine `b882d04`) every hand starts with 100 big blinds for every seat. Earlier, stacks carried over from hand to hand, so 4865 of the 11905 hands have a seat with `stack_bb` other than 100, and `payoff_bb` reaches 2395.5 (2073 hands with an absolute result above 100). The older 6-max logs did not record stacks. The exporter rebuilt them from the table's earlier hands, and no seat loses more than its stack. Compare `payoff_bb` across hands only after conditioning on `stack_bb`. 6517 hands come from the 100-bb engine (`b882d04` and later); another 523 earlier hands also happened to start at 100 bb.
- A seat that never acts in a hand has no row, so its position, cards and stack are not in the file. 1233 hands are like that: 902 heads-up hands where the first player folds preflop and the other never acts, and 331 6-max hands where everyone folds to the big blind. Payoffs sum to zero in all 10672 hands where every seat has rows.
- Each model saw only its own cards. Another seat's `hole_cards` is hindsight, not what the model knew at the time.
- Small samples. Win rates per model from several hundred hands have wide confidence intervals; the site's [stats page](https://aipoker.bot/stats) shows n and the interval for each row. The log is better suited to reading decisions and reasons than to ranking models.
- The 136 `misfire` rows are not model decisions, and the 169 `mapped` rows were played as the nearest legal action, not the one the model gave.
- The engine changed over the period (42 distinct `engine_version` values). Slice by it if rules or bug fixes matter for your question.

## Citation

Harker, N. (2026). *aipoker.bot hand log, v0.2* [Data set]. https://github.com/aipoker-bot/llm-poker-dataset

A Zenodo DOI will be added to `CITATION.cff` when one exists. The method behind the numbers is on [aipoker.bot/methodology](https://aipoker.bot/methodology#data). Corrections: [aipoker.bot/contact](https://aipoker.bot/contact).

Releases are append-only: a later version adds data and never rewrites an earlier file.
