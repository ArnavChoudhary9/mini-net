# 02 — Controller

> Source: [`examples/02_controller.py`](https://github.com/)

Two nodes sharing a single wire, driven through a `Controller` you call
from Python.

```bash
python examples/02_controller.py
```

## The topology

```text
        +-------+                          +-------+
        | alice |-- eth0 -- link -- eth0 --|  bob  |
        +-------+                          +-------+
```

Both interfaces connect to the **same** `Wire`. This models a bus / coax
link: everyone shares one medium. Sorting out who reads what is part of
the [duplex challenge](../duplex-challenge.md).

## Building the world

```python
world = Internet("world")

alice = world.AddNode("alice")
bob   = world.AddNode("bob")
link  = world.AddWire("link", Capacity=8)

alice.AddInterface("eth0").Connect(link)
bob.AddInterface("eth0").Connect(link)
```

Notice `AddInterface().Connect(link)` — chaining works because
`AddInterface` returns the interface.

## Driving it from a Controller

```python
ctrl = Controller(world)

ctrl.Inspect()                                          # initial state

ctrl.Send("alice", b"Hello, Bob!",  Dst="bob", Seq=1)
ctrl.Send("alice", b"How are you?", Dst="bob", Seq=2)

ctrl.Tick()                                             # TX -> wire
ctrl.Drain("bob")                                       # RX is empty

ctrl.Send("bob", b"Hi Alice!", Dst="alice", Seq=1)
ctrl.Tick()
ctrl.PeekWire("link")                                   # all 3 packets in flight
```

## What you'll see

After one tick, the wire holds Alice's two packets. After the second tick,
Bob's reply joins them. **Nothing leaves the wire** because the receive
side of `Interface.Tick()` is unimplemented.

## Takeaways

- `Internet` owns time. Everything advances together.
- `Controller` is "just" a wrapper that prints what's happening — but
  that's exactly what you need when debugging a simulator.
- A shared wire holds packets from both directions. Distinguishing
  "my packets" from "their packets" is a real problem to solve.
