# Node

A **device** (host, router, switch, …) that owns one or more interfaces.

```python
node = Node("alice")
eth0 = node.AddInterface("eth0")
node.Send(packet)        # uses interface 0 by default
node.Tick()              # ticks all interfaces
pkt = node.Receive()
```

Source: [`network/node.py`](https://github.com/)

## What a node is

A `Node` is just a named container of `Interface`s. It is intentionally thin —
all the real work happens at the interface level. The node provides:

- A namespace (so interfaces get nice names like `alice/eth0`)
- A bulk `Tick()` that advances every interface in one call
- Index-based shortcuts for `Send`/`Receive` so simple examples stay short

A node with two interfaces is conceptually a **router** or **switch**;
a node with one interface is a **host**. mini-net does not distinguish
them — what matters is how you wire them together and what code you run.

## API

| Method / Property            | What it does                                               |
| ---------------------------- | ---------------------------------------------------------- |
| `AddInterface(name)`         | Create + attach + return an `Interface`                    |
| `FlushTx()`                  | Phase 1: flush every interface's TX queue onto its wire    |
| `DrainRx()`                  | Phase 2: drain every interface's wire into its RX queue    |
| `Tick()`                     | Convenience: `FlushTx()` then `DrainRx()`                  |
| `Send(packet, iface=0)`      | Shortcut for `Interfaces[iface].Send(packet)`              |
| `Receive(iface=0)`           | Shortcut for `Interfaces[iface].Receive()`                 |
| `Interfaces`                 | Snapshot list of attached interfaces (for inspection)      |
| `Name`                       | Node name                                                  |

## Example

```python
from network import Node, Wire, Packet

alice = Node("alice")
eth0 = alice.AddInterface("eth0")        # named alice/eth0

wire = Wire("link")
eth0.Connect(wire)

alice.Send(Packet(Data=b"ping", Src="alice", Dst="bob"))
alice.Tick()
print(wire.Peek())
# [Packet(Seq=0, Src='alice', Dst='bob', Data=b'ping')]
```

## What's next

A loose collection of nodes is not a "world" yet. To advance time
coherently across the whole network, you put them inside an
[Internet](./internet.md).
