# 03 — REPL

> Source: [`examples/03_repl.py`](https://github.com/)

Same topology as the controller example, but driven from an interactive
prompt instead of code.

```bash
python examples/03_repl.py
```

## Quickest launch

You don't actually need this example file. The same prompt is one
shell command away:

```bash
python -m network                  # 2 nodes + 1 wire
python -m network ethernet         # switched LAN
python -m network lossy            # 30% lossy link
```

`examples/03_repl.py` is just the same topology built explicitly, so
you can see how it is wired.

## What you get

```text
mini-net controller 'ctrl' attached to 'world'
type 'help' for commands, 'quit' to exit

ctrl@world>
```

Type `help` to see the full list. The most common pattern:

```text
ctrl@world> nodes
  alice
    [0] alice/eth0  TX=0 RX=0  wire='link'
  bob
    [0] bob/eth0  TX=0 RX=0  wire='link'

ctrl@world> send alice "Hello, Bob!" bob 1
[ctrl] -> alice eth0.Send  Packet(Seq=1, Src='alice', Dst='bob', Data=b'Hello, Bob!')

ctrl@world> tick
[ctrl] tick x1
[ctrl] ----- state @ tick 1 -----
      wire  link                 [1 in flight]
            - Packet(Seq=1, Src='alice', Dst='bob', Data=b'Hello, Bob!')
      ...

ctrl@world> peek link
[ctrl] wire 'link' carries 1:
      - Packet(Seq=1, Src='alice', Dst='bob', Data=b'Hello, Bob!')

ctrl@world> drain bob
[ctrl] <- bob eth0 RX empty
```

## Toggle logging live

Set the log level without leaving the REPL:

```text
ctrl@world> log debug
  logging: debug
ctrl@world> tick
INFO     network.internet: [world] ===== TICK 2 =====
DEBUG    network.wire: [link] Tick  (buffered=1)
DEBUG    network.node: [alice] Tick
...
```

See the [Logging](../logging.md) guide for everything that's loggable.

## Quoting

Data with spaces uses shell-style quotes (`shlex.split`):

```text
ctrl@world> send alice "hello world" bob 1
```

## Why a REPL?

Two reasons:

1. **Speed of iteration.** Tweak the world, send a packet, tick, look,
   repeat — all without restarting Python.
2. **It forces clarity.** If you can drive your simulation from text
   commands, your mental model is concrete.

## Takeaways

- The REPL is purely a layer on top of the same `Controller` methods.
- Once you implement duplex, `drain bob` will start returning packets.
  No code in the REPL has to change.
