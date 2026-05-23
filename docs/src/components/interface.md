# Interface

A **port on a node** with a TX queue, an RX queue, and a connected Wire.

```python
iface = Interface(Name="alice/eth0")
iface.Connect(wire)
iface.Send(packet)
iface.Tick()
pkt = iface.Receive()
```

Source: [`network/interface.py`](https://github.com/)

## The two-queue model

```text
        application
            |  Send()                        Receive()  ^
            v                                           |
        +---------+   FlushTx()   +-------+   DrainRx() |
        | TxQueue | ------------> | Wire  | ----------> | RxQueue
        +---------+               +-------+
```

The TX queue lets the application call `Send()` whenever it wants, even
between ticks. The RX queue accumulates received packets until the
application reads them.

A tick happens in **two phases**:

1. **`FlushTx()`** — every packet in TX is put on the wire, tagged with
   the interface's name so the sender won't accidentally read it back.
2. **`DrainRx()`** — every frame on the wire whose sender is someone
   else is moved into RX (and removed from the wire).

`Tick()` is just the convenience that runs both phases. Inside an
`Internet`, the world calls `FlushTx` on *all* interfaces first, then
`DrainRx` on *all* interfaces — so two nodes can exchange packets in a
single global tick.

## Why a sender tag?

Both interfaces share one wire. Without a tag, an interface would read
back the packets it just transmitted. The wire stores `(Packet, sender)`
frames; the interface skips frames where `sender == self.Name`.

## API

| Method / Property | What it does                                            |
| ----------------- | ------------------------------------------------------- |
| `Connect(wire)`   | Attach this interface to a wire                         |
| `Send(packet)`    | Enqueue for transmission; returns `False` if no wire    |
| `Receive()`       | Pop the next packet from RX; returns `None` if empty    |
| `FlushTx()`       | Phase 1 of a tick: TX queue → wire (with sender tag)    |
| `DrainRx()`       | Phase 2 of a tick: wire → RX queue (skipping own)       |
| `Tick()`          | Convenience: `FlushTx()` then `DrainRx()`               |
| `Connected`       | `True` when a wire is attached                          |
| `TxSize`          | Number of packets waiting to be sent                    |
| `RxSize`          | Number of packets waiting to be read by the application |
| `WireName`        | Name of the connected wire, or `'<none>'`               |
| `Name`            | Full interface name, e.g. `alice/eth0`                  |

## Naming convention

Interfaces are typically created via `Node.AddInterface("eth0")`. The
node prefixes its own name, so the resulting `Interface.Name` looks like
`alice/eth0`. This is purely a human-friendly label — nothing in the code
parses it.

## Example

```python
from network import Interface, Wire, Packet

wire = Wire("link")
iface = Interface("alice/eth0")
iface.Connect(wire)

iface.Send(Packet(Data=b"hi", Src="alice", Dst="bob"))
print(iface.TxSize)   # 1
iface.Tick()
print(iface.TxSize)   # 0
print(wire.Size)      # 1
```

## What's next

You usually don't make bare interfaces. A [Node](./node.md) owns them.
