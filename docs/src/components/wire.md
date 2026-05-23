# Wire

A **one-directional FIFO buffer** between two points. The closest mini-net
gets to a "physical medium".

```python
wire = Wire(Name="link", Capacity=8, DropRate=0.0)
wire.Put(packet, Sender="alice/eth0")   # tags the packet with its source
wire.Get()                              # returns the next packet, or None
wire.Peek()                             # non-consuming snapshot
wire.Frames()                           # snapshot of (packet, sender) tuples
wire.Consume(frame)                     # remove a specific frame
wire.Tick()                             # placeholder for propagation delay
```

Source: [`network/wire.py`](https://github.com/)

## Mental model

Think of the wire as a tube. You put a packet in one end with `Put()`; it
comes out the other end with `Get()`. The tube has a fixed `Capacity` — if
it's full, new packets are dropped (and a counter is bumped).

```text
   Put() -->  [pkt][pkt][pkt]   <-- Get()
```

The wire does **not** know which end is the sender or receiver. That is up
to whoever connects interfaces to wires. This is intentional: it lets you
build half-duplex, full-duplex, or bus-style topologies on top of the same
primitive.

## API

| Method / Property        | What it does                                                  |
| ------------------------ | ------------------------------------------------------------- |
| `Put(packet, Sender="")` | Append a packet tagged with a sender; `False` if dropped      |
| `Get()`                  | Pop the next packet; returns `None` if empty                  |
| `Frames()`               | Non-destructive list of `(packet, sender)` frames             |
| `Consume(frame)`         | Remove a specific frame (used by the receiving interface)     |
| `Peek()`                 | Non-destructive list of just the packets                      |
| `Tick()`                 | A hook for future propagation delay (currently a no-op)       |
| `Size`                   | Number of packets currently in the buffer                     |
| `Empty`                  | `True` when the buffer is empty                               |
| `Dropped`                | Count of packets dropped (capacity + random)                  |
| `DropRate`               | Probability `[0.0, 1.0]` of dropping each `Put()`             |
| `Name`                   | Human-readable label, used in logs and the Controller         |

## Drop rate

Set `DropRate` to simulate a lossy link. On every `Put`, the wire rolls a
random number and drops the packet with that probability — the
`Dropped` counter increments and a warning is logged.

```python
flaky = Wire("flaky", DropRate=0.3)   # 30% loss
```

Or via `Internet`:

```python
flaky = world.AddWire("flaky", DropRate=0.3)
```

You can use this to motivate building a reliable transport on top of an
unreliable link — set `Seq` on outgoing packets and have the receiver
acknowledge them.

## Example

```python
from network import Wire, Packet

wire = Wire(Name="alice->bob")
wire.Put(Packet(Data=b"first",  Seq=1))
wire.Put(Packet(Data=b"second", Seq=2))

print(wire.Get())   # Packet(Seq=1, ..., Data=b'first')
print(wire.Get())   # Packet(Seq=2, ..., Data=b'second')
print(wire.Get())   # None
```

## What's next

A wire is useful, but you don't talk to it directly. You connect an
[Interface](./interface.md) to it and let the interface manage the queues.
