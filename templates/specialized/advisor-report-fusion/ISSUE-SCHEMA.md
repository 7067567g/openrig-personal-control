# ISSUE / CLAIM REGISTER SCHEMA

`reports/claim-register.jsonl` 每行必须是一个 JSON 对象。推荐字段：

| 字段 | 必填 | 允许值 / 说明 |
| --- | --- | --- |
| `id` | 是 | `AFC-NNN`，全 run 唯一 |
| `title` | 是 | 一句话描述底层问题/机制 |
| `claim_type` | 是 | `fact` / `inference` / `recommendation` / `risk` / `change` |
| `sources` | 是 | 非空数组，如 `["OC:P0-1", "DSH:P0-2", "CMP:7.1"]` |
| `evidence_status` | 是 | `verified` / `partial` / `stale` / `unverified` |
| `disposition` | 是 | `accept_now` / `accept_next` / `park` / `reject` / `already_done` |
| `wave` | 处置需要 | `W0` / `W1` / `W2` / `W3` / `none` |
| `owner` | accept_* 需要 | `TDO` / `PMO` / `MAIN` / `QA` |
| `action` | 是 | 具体动作，不是“关注/优化” |
| `acceptance` | accept_* 需要 | 可复跑命令/断言 |
| `reject_reason` | reject 需要 | 为什么不做 |
| `trigger` | park 需要 | 重启条件 |
| `notes` | 否 | 冲突、反证、边界 |

`check_fusion.py` 会机械检查这些字段、唯一 ID 和来源格式；它不判断技术结论是否正确，技术正确性仍由 QA 独立复核。
