# Logging

mini-net logs through the standard `logging` module. The library follows
best practice: it stays **silent by default** and only emits records when
you opt in.

## Quick enable

```python
import logging
from network.log import EnableLogging

EnableLogging(logging.DEBUG)         # very verbose
EnableLogging(logging.INFO)          # just the important stuff
EnableLogging(logging.WARNING)       # only problems
```

Inside the REPL:

```text
ctrl@world> log debug
ctrl@world> log info
ctrl@world> log warning
ctrl@world> log off
```

## What gets logged

| Logger              | Level   | Example                                                       |
| ------------------- | ------- | ------------------------------------------------------------- |
| `network.internet`  | INFO    | `[world] ===== TICK 3 =====`                                  |
| `network.internet`  | INFO    | `[world] registered node 'alice'`                             |
| `network.node`      | INFO    | `[alice] added interface 'alice/eth0'`                        |
| `network.node`      | DEBUG   | `[alice] Tick`                                                |
| `network.interface` | INFO    | `[alice/eth0] connected to wire 'link'`                       |
| `network.interface` | INFO    | `[alice/eth0] TX -> [link]: Packet(...)`                      |
| `network.interface` | DEBUG   | `[alice/eth0] queued for TX: Packet(...)`                     |
| `network.interface` | WARNING | `[alice/eth0] Send failed — no wire attached`                 |
| `network.wire`      | DEBUG   | `[link] Put Packet(...)  (queued=2)`                          |
| `network.wire`      | DEBUG   | `[link] Get Packet(...)  (remaining=1)`                       |
| `network.wire`      | WARNING | `[link] buffer full — dropped Packet(...)`                    |
| `network.controller`| INFO    | `[ctrl] attached to 'world'`                                  |

## Filtering by source

Every module has its own logger, so you can dial them in individually:

```python
import logging
logging.getLogger("network.wire").setLevel(logging.DEBUG)
logging.getLogger("network.interface").setLevel(logging.WARNING)
```

This is useful when you're debugging a specific layer.

## Format

`EnableLogging()` installs a simple stdout handler with the format:

```text
LEVEL    logger.name: message
```

Override by attaching your own handler before calling `EnableLogging`,
or build your config from scratch using stdlib `logging`.

## Silencing

```python
from network.log import DisableLogging
DisableLogging()
```

Or inside the REPL:

```text
ctrl@world> log off
```
