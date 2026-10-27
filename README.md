# aipoker.bot hand log, v0.1

Every betting action from poker hands that people played on [aipoker.bot](https://aipoker.bot) against language models and classic scripted bots. One JSONL row per action. For the LLM seats each row carries the model id, the frozen prompt version, the model's own one-line reason, cost and latency.

- 57065 rows, 5398 hands, 247 sessions, three formats (6-max No-Limit Hold'em, heads-up No-Limit Hold'em, heads-up Pot-Limit Omaha).
- 19293 rows are decisions of 38 language models, all on prompt 1.2.1. The rest are the human (13914), scripted bots (15398) and scripted stand-ins that took over an LLM seat when its daily quota or the budget ran out (8460).
- Hands were logged from 2026-08-19 to 2026-10-27 (UTC), about 95% of them since 2026-09-28. Rows carry no timestamps.
- License CC BY 4.0. Snapshot of the event log: 2026-10-27 15:51 UTC.

This is a log of people playing, not a tournament. Line-ups, formats and the number of hands per model are whatever the players got.

## Files

- `data/human.jsonl`: the dataset. sha256 `956bd199e7fa207402916f092fc9202a4487c36c1f88f2c007dfcc4a09304f87`.
- `scripts/export_dataset.py`: the exporter that wrote it. It reads the site's event log, so it is reference only and won't run on this file.
- `CHECKS.md`: the checks run on the file before release (privacy scan, hand ids, zero-sum payoffs, card uniqueness, row counts) and their results.
- `CITATION.cff`, `CHANGELOG.md`.

## Rows

| field | type | meaning |
|---|---|---|
| `hand` | string | `<sha256 of the session id, first 12 hex>:<table>:<hand number>`. The table is counted from 1 inside a session, because hand numbers restart on every table. Rows of one hand are consecutive. |
| `session_type` | string | `human` in v0.1: hands played by a visitor. |
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
| `prompt_version` | string | LLM rows only. Frozen prompt, always `1.2.1` in v0.1. |
| `reasoning` | string | LLM rows only. The model's written reason, verbatim, 20 words or fewer. It explains the answer; it is not a record of what the model computed. Empty on 76 rows. |
| `legal_actions` | list | LLM rows only. What the model was allowed to do: `fold`, `call`, `raise`. |
| `outcome` | string | LLM and stand-in rows. `ok`; `mapped` (illegal answer, played as the nearest legal action); `misfire` (no usable answer, the seat checked or folded); `standin` (a scripted bot played this LLM seat). |
| `cost_usd` | number | LLM rows only. Cost of the API call. Missing on 27 rows. |
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
| 6max_nlhe | 4223 | 51406 |
| hu_nlhe | 1148 | 5526 |
| hu_plo | 27 | 133 |

1399 of the 5398 hands went to showdown. LLM rows by outcome: ok 19145, mapped 74, misfire 74.

Decisions per model. Only two models have 1000 or more; anything said about the others rests on a few hundred decisions.

<details>
<summary>38 models</summary>

| model_id | decisions | hands | 6max_nlhe | hu_nlhe | hu_plo |
|---|---:|---:|---:|---:|---:|
| openai/gpt-6-astra | 1358 | 655 | 570 | 788 | 0 |
| z-ai/glm-4.7-flash | 1259 | 427 | 1259 | 0 | 0 |
| deepseek/deepseek-v4-flash | 846 | 204 | 846 | 0 | 0 |
| minimax/minimax-m3 | 771 | 359 | 754 | 17 | 0 |
| anthropic/claude-haiku-5.5 | 764 | 296 | 718 | 46 | 0 |
| z-ai/glm-5.3 | 727 | 314 | 727 | 0 | 0 |
| x-ai/grok-4.7 | 705 | 326 | 251 | 436 | 18 |
| anthropic/claude-opus-5.5 | 676 | 324 | 376 | 300 | 0 |
| z-ai/glm-5.3-flash | 660 | 302 | 660 | 0 | 0 |
| openai/gpt-5.6-terra | 647 | 343 | 634 | 13 | 0 |
| google/gemma-4-31b-it | 641 | 262 | 641 | 0 | 0 |
| x-ai/grok-4.6 | 637 | 284 | 164 | 427 | 46 |
| qwen/qwen3.8-27b | 634 | 271 | 634 | 0 | 0 |
| google/gemini-3.1-pro-preview | 627 | 402 | 499 | 128 | 0 |
| qwen/qwen3.7-plus | 617 | 332 | 612 | 0 | 5 |
| qwen/qwen3.8-flash | 607 | 302 | 607 | 0 | 0 |
| openai/gpt-oss-20b | 556 | 270 | 556 | 0 | 0 |
| openai/gpt-5.4-mini | 554 | 165 | 554 | 0 | 0 |
| deepseek/deepseek-v4-pro-0813 | 527 | 255 | 524 | 3 | 0 |
| mistralai/ministral-14b-2512 | 502 | 211 | 502 | 0 | 0 |
| anthropic/claude-haiku-4.5 | 466 | 224 | 464 | 2 | 0 |
| deepseek/deepseek-v4.1-flash | 466 | 183 | 444 | 22 | 0 |
| mistralai/mistral-medium-3-5 | 412 | 218 | 397 | 15 | 0 |
| moonshotai/kimi-k3 | 409 | 196 | 405 | 4 | 0 |
| anthropic/claude-fable-5.1 | 406 | 219 | 377 | 29 | 0 |
| qwen/qwen3.8-max-0902 | 393 | 243 | 393 | 0 | 0 |
| mistralai/mistral-large-4-0 | 391 | 182 | 391 | 0 | 0 |
| openai/gpt-6.1-sol | 365 | 241 | 354 | 11 | 0 |
| ibm-granite/granite-4.2-8b | 341 | 336 | 341 | 0 | 0 |
| anthropic/claude-sonnet-5.5 | 311 | 169 | 311 | 0 | 0 |
| openai/gpt-6-luna | 284 | 156 | 284 | 0 | 0 |
| google/gemini-3.8-flash | 283 | 195 | 276 | 7 | 0 |
| openai/gpt-5.6-sol | 148 | 69 | 54 | 94 | 0 |
| anthropic/claude-sonnet-5 | 133 | 81 | 133 | 0 | 0 |
| openai/gpt-5.6-luna | 94 | 48 | 94 | 0 | 0 |
| google/gemini-3.7-flash | 61 | 41 | 61 | 0 | 0 |
| anthropic/claude-opus-5 | 12 | 5 | 11 | 1 | 0 |
| mistralai/mistral-large-2512 | 3 | 3 | 3 | 0 | 0 |

</details>

## Left out

6152 hands were logged by the site over the same period; 754 are not in the file.

- 321 hands against Slumbot. Slumbot plays on its own server, so the log has the human's moves and not the opponent's. A hand without the opponent's moves is not a hand of this dataset.
- 792 benchmark hands (`session_type` bench, 9 sessions on 2026-09-14). All of them were against Slumbot, so v0.1 has no bench rows.
- 235 hands without exactly one end record, mostly hands abandoned midway.
- 35 hands that could not be placed on a table with certainty.
- 163 early 6-max hands whose starting stacks could not be rebuilt.

Also left out: the site's own test sessions, and anything that identifies a player. Session ids are hashed; the file has no IP, cookie, fingerprint, email or URL (`CHECKS.md` lists the scans).

## Limitations

- Stacks. Since 2026-10-27 (engine `b882d04`) every hand starts with 100 big blinds for every seat. Earlier, stacks carried over from hand to hand, so 4865 of the 5398 hands have a seat with `stack_bb` other than 100, and `payoff_bb` reaches 2395.5 (873 hands with an absolute result above 100). The older 6-max logs did not record stacks. The exporter rebuilt them from the table's earlier hands, and no seat loses more than its stack. Compare `payoff_bb` across hands only after conditioning on `stack_bb`. Only 10 hands come from the 100-bb engine.
- A seat that never acts in a hand has no row, so its position, cards and stack are not in the file. 423 hands are like that: 224 heads-up hands where the first player folds preflop and the other never acts, and 199 6-max hands where everyone folds to the big blind. Payoffs sum to zero in all 4975 hands where every seat has rows.
- Each model saw only its own cards. Another seat's `hole_cards` is hindsight, not what the model knew at the time.
- Small samples. Win rates per model from a few hundred hands have wide confidence intervals; the site's [stats page](https://aipoker.bot/stats) shows n and the interval for each row. The log is better suited to reading decisions and reasons than to ranking models.
- The 74 `misfire` rows are not model decisions, and the 74 `mapped` rows were played as the nearest legal action, not the one the model gave.
- The engine changed over the period (28 distinct `engine_version` values). Slice by it if rules or bug fixes matter for your question.

## Citation

Harker, N. (2026). *aipoker.bot hand log, v0.1* [Data set]. https://github.com/aipoker-bot/llm-poker-dataset

A Zenodo DOI will be added to `CITATION.cff` when one exists. The method behind the numbers is on [aipoker.bot/methodology](https://aipoker.bot/methodology#data). Corrections: [aipoker.bot/contact](https://aipoker.bot/contact).

Releases are append-only: a later version adds data and never rewrites an earlier file.
