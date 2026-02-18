# Memory Summary Sliding Window 设计草案

## 目标

把当前“超过阈值后几乎每条消息都触发 summary”的行为，改成稳定的滑动窗口批量压缩，降低 token 成本，同时保留近期对话连贯性。

## 术语和参数

- `context_size`:
  - 含义: 每次给模型的历史消息条数上限。
  - 例子: `context_size = 75`
- `compression_window_size`:
  - 含义: 每累计 N 条可压缩历史消息，触发一次 summary。
  - 例子: `compression_window_size = 12`
- `tail_keep_size`:
  - 含义: 永远不压缩的最近尾部消息条数，用于保证短期上下文。
  - 约束: `tail_keep_size < context_size`
  - 例子: `tail_keep_size = 40`
- `compression_cooldown_sec`:
  - 含义: 时间节流；即使未达到 `compression_window_size`，到达冷却时间也可触发一次增量压缩。
  - 例子: `compression_cooldown_sec = 900`
- `compression_hard_limit`:
  - 含义: 可压缩积压超过该值时强制触发，避免长期不压缩。
  - 例子: `compression_hard_limit = 30`

## 状态变量

- `last_consolidated`:
  - 含义: 已压缩到的消息下标（开区间右边界）。
- `last_consolidated_at`:
  - 含义: 最近一次压缩完成时间戳。
- `is_consolidating`:
  - 含义: 当前是否有压缩任务在运行（并发锁）。
- `pending_consolidation`:
  - 含义: 压缩运行期间是否有新触发请求，结束后补跑一次。

## 触发判定

每次收到新消息时，计算:

1. `total = len(session.messages)`
2. `compress_end = total - tail_keep_size`
3. `delta = compress_end - last_consolidated`

早停:

- 若 `compress_end <= last_consolidated`，不触发。

触发条件（满足任一条）:

- `delta >= compression_window_size`
- `delta >= compression_hard_limit`
- `delta > 0 and now - last_consolidated_at >= compression_cooldown_sec`

并发行为:

- 若 `is_consolidating = true`，只设置 `pending_consolidation = true`，不重复启动任务。
- 当前任务结束后，若 `pending_consolidation = true`，清零后立刻再跑一轮判定。

## 压缩区间

summary 输入区间:

- `messages[last_consolidated : compress_end]`

压缩完成后:

- `last_consolidated = compress_end`
- `last_consolidated_at = now`

## ASCII 图示

### 1) 窗口分段

```text
messages index:  0                                      total-1
                 |-----------------------------------------|
                 |      older (candidate)      |  tail_keep |
                 |------------------------------|-----------|
                 ^                              ^
                 last_consolidated              compress_end (= total - tail_keep_size)

delta = compress_end - last_consolidated
trigger when delta reaches compression_window_size (or cooldown/hard_limit)
```

### 2) 触发节奏（示例）

```text
params:
  context_size=75
  tail_keep_size=40
  compression_window_size=12

time --->   m1 m2 m3 ... m12 ... m24 ... m36
delta --->   1  2  3 ... 12  -> trigger #1
                     reset to 0 after consolidation
                     1 ... 12 -> trigger #2
```

### 3) 并发去重

```text
msg arrives -> should_trigger = true
             -> is_consolidating?
                  no  -> start consolidation task
                  yes -> pending_consolidation = true

task done -> pending_consolidation?
               no  -> exit
               yes -> pending_consolidation = false; rerun once
```

## 默认建议

- `context_size = 75`
- `tail_keep_size = 40`
- `compression_window_size = 12`
- `compression_cooldown_sec = 900`
- `compression_hard_limit = 30`

## 兼容与迁移

- 保留现有 `last_consolidated` 字段。
- 新增可选字段:
  - `last_consolidated_at` (ISO datetime)
  - `pending_consolidation` (runtime only, not required to persist)
- 未配置新参数时，使用默认值，不影响现有配置文件加载。
