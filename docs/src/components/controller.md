# Controller

A **debugger / inspector** for an `Internet`. Use it from Python code or
launch the interactive REPL.

```python
ctrl = Controller(world)
ctrl.Send("alice", b"hi", Dst="bob")
ctrl.Tick()
ctrl.Inspect()
ctrl.Drain("bob")
ctrl.Repl()                   # interactive console
```

Source: [`network/controller.py`](https://github.com/)

## Two ways to drive it

### Programmatically

Every command is a regular Python method. This is great when you want to
script a scenario, write a test, or build an automated check.

### Interactively

```python
Controller(world).Repl()
```

Drops you at a prompt where you can type commands. Same operations, but
faster to iterate on when you're exploring.

```text
ctrl@world> send alice "hello" bob
ctrl@world> tick
ctrl@world> peek link
ctrl@world> drain bob
ctrl@world> quit
```

## Python API

| Method                              | What it does                                    |
| ----------------------------------- | ----------------------------------------------- |
| `Send(node, data, Dst, Seq, Iface)` | Build a `Packet` and queue it on a node         |
| `Tick(Times=1, ShowState=True)`     | Advance the world and (by default) print state  |
| `Drain(node, Iface=0)`              | Read every packet in RX and print each          |
| `Inspect()`                         | Full snapshot of every wire + interface         |
| `PeekWire(name)`                    | Print every packet currently in transit         |
| `Repl()`                            | Start the interactive console                   |

## REPL commands

| Command                                    | Alias             | Description                          |
| ------------------------------------------ | ----------------- | ------------------------------------ |
| `send <node> <data> [dst] [seq]`           | `s`               | Queue a raw packet on a node         |
| `frame <node> <dst_mac> <data> [seq]`      | `f`               | Queue an Ethernet frame on a host    |
| `tick [n]`                                 | `t`               | Advance the world by n ticks         |
| `drain <node> [iface]`                     | `d`               | Read + print RX queue                |
| `peek <wire>`                              | `p`               | Show packets in flight on a wire     |
| `inspect`                                  | `i`               | Full world snapshot                  |
| `mactable <switch>`                        | `m`               | Show a switch's learned MAC table    |
| `nodes`                                    |                   | List nodes & interfaces              |
| `wires`                                    |                   | List wires & their sizes             |
| `log <debug\|info\|warning\|off>`          |                   | Live-toggle log verbosity            |
| `help`                                     | `?`               | Command reference                    |
| `quit`                                     | `q`, `exit`, `^D` | Exit                                 |

The `frame` command builds an `EthernetFrame` using the host's
`EthernetInterface.SendFrame()`. Use `broadcast` as the destination to
target every other port on a switch:

```text
ctrl@lan> frame alice broadcast "anybody home?" 1
```

Strings with spaces use shell-style quoting:

```text
ctrl@world> send alice "Hello, Bob!" bob 1
```

## Why this exists

A simulator is only useful if you can see what's happening inside it.
The Controller's job is to make the world's state visible. As soon as
something doesn't behave the way you expected, type `inspect` and look at
the queues.

## What's next

Now you have all the pieces. Try [walkthrough 03 — REPL](../walkthrough/repl.md),
then take the [duplex challenge](../duplex-challenge.md).
