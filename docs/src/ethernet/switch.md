# Switch

A `Switch` is a `Node` that **forwards frames between its ports** based
on destination MAC. It is the heart of any non-trivial Ethernet LAN.

```python
sw = world.AddNode("sw", Cls=Switch, Ports=4)
```

Source: [`network/ethernet.py`](https://github.com/)

## What a switch does

On every tick, after `DrainRx` has moved frames off the wires into the
ports' RX queues, the switch inspects each frame it received and:

1. **Learns** — records `frame.Src → in_port` in its MAC table.
2. **Forwards** —
   - If `frame.Dst` is the broadcast address, the frame is **flooded**
     to every port *except* the one it came in on.
   - If `frame.Dst` is in the MAC table, the frame is **forwarded** out
     exactly that port.
   - If `frame.Dst` is unknown, the frame is also **flooded** — this is
     what every real switch does on a cache miss.

The frame is dropped silently if `frame.Dst` is on the same port it
arrived on (no point sending it back where it came from).

## Why learning works

Watch what happens when Alice first sends to Bob through a fresh switch:

```text
Tick 1
  alice -> wire_a -> port0 (switch)
  switch: "I see aa:aa:aa:aa:aa:aa on port0 — learn"
  switch: "I don't know bb:bb:bb:bb:bb:bb — flood to port1, port2, ..."

Tick 2
  port1 -> wire_b -> bob       (gets Alice's frame)
  port2 -> wire_c -> charlie   (also gets it — unwanted but harmless)
```

When Bob replies, the switch:

```text
Tick 3
  bob -> wire_b -> port1 (switch)
  switch: "I see bb:bb:bb:bb:bb:bb on port1 — learn"
  switch: "I know aa:aa:aa:aa:aa:aa lives on port0 — forward there only"

Tick 4
  port0 -> wire_a -> alice
```

Now the table has both entries. Future Alice-to-Bob traffic is
forwarded directly, never flooded.

## Inspecting the table

```python
sw.MacTable
# {'aa:aa:aa:aa:aa:aa': 0, 'bb:bb:bb:bb:bb:bb': 1}
```

Or from the REPL:

```text
ctrl@lan> mactable sw
  sw MAC table:
    aa:aa:aa:aa:aa:aa -> port0
    bb:bb:bb:bb:bb:bb -> port1
```

## API

| Member                | What it does                                  |
| --------------------- | --------------------------------------------- |
| `Switch(Name, Ports)` | Construct a switch with N ports (default 4)   |
| `Tick()`              | Inherited; runs the learning + forwarding     |
| `MacTable`            | Snapshot of the learned MAC -> port mapping   |

The ports themselves are plain `Interface`s — switches are transparent
at L2 so the ports do not need their own MACs.

## Latency through a switch

A frame takes **2 ticks** to traverse a switch:

- Tick N: frame put on inbound wire → switch reads it during DrainRx →
  switch queues forwarded copy in the outgoing port's TX queue
- Tick N+1: TX queue flushed onto outbound wire → destination reads it

This is the discrete-event equivalent of a real switch's store-and-
forward delay.

## What's next

Try the [walkthrough](../walkthrough/ethernet.md), or look at
[stretch goals](../duplex-challenge.md#stretch-goals) for ideas (multi-hop
routing, IP, ARP, …).
