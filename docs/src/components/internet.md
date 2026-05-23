# Internet

The **simulation world**. Owns every node and every wire, and is the single
source of truth for advancing time.

```python
world = Internet("world")
alice = world.AddNode("alice")
link  = world.AddWire("link")
world.Tick()                       # ticks all wires, then all nodes
world.Tick(Times=10)               # ten ticks
```

Source: [`network/internet.py`](https://github.com/)

## Why a separate "world" class?

You *could* drive a simulation by calling `node.Tick()` on each node in turn.
For two nodes that works fine — but it leads to subtle ordering bugs as
soon as you have more than one wire.

`Internet.Tick()` is **two-phase**:

1. Tick every wire (propagation hook).
2. **FlushTx** on every node — all outgoing packets land on wires.
3. **DrainRx** on every node — all wires are read after everyone has
   finished transmitting.

The split matters: if you flushed and drained one node at a time, then
the first node to tick would put its packets on the wire and then read
the wire before any other node has flushed — so it would never receive
anything sent in the same tick. By flushing every node first and only
then draining, two nodes can exchange packets within a single global
tick. This is exactly how serious network simulators (ns-3 et al.) work.

## API

| Method / Property      | What it does                                         |
| ---------------------- | ---------------------------------------------------- |
| `AddNode(name)`        | Create + register + return a `Node`                  |
| `AddWire(name, cap=…)` | Create + register + return a `Wire`                  |
| `FindNode(name)`       | Look up a node by name; raises `KeyError` if missing |
| `FindWire(name)`       | Look up a wire by name; raises `KeyError` if missing |
| `Tick(Times=1)`        | Advance the world by N ticks                         |
| `Nodes`                | Snapshot list of all nodes                           |
| `Wires`                | Snapshot list of all wires                           |
| `TickCount`            | Total number of ticks since construction             |
| `Name`                 | World name (used in logs)                            |

## Example

```python
from network import Internet

world = Internet("lab")
alice = world.AddNode("alice")
bob   = world.AddNode("bob")
link  = world.AddWire("link")

alice.AddInterface("eth0").Connect(link)
bob.AddInterface("eth0").Connect(link)

world.Tick(5)
print(world.TickCount)     # 5
```

## What's next

Once you have a world, you usually want a way to poke at it. Enter the
[Controller](./controller.md).
