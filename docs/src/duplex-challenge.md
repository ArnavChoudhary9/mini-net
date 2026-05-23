# Duplex Challenge

> **Solved in-tree.** The current `Interface.Tick()` implements full-duplex
> using a sender-tagged wire and a two-phase tick at the `Internet` level.
> This page documents the design and points at things to try next.

## The original problem

A single shared `Wire` carries packets between two interfaces in **both**
directions. If `Interface.Tick()` naively reads from the wire after
transmitting, it will pick up packets it just put there itself. And if
the tick order is `alice → bob`, then a packet bob sends in his tick
cannot reach alice until the next tick (alice is already done).

## The solution mini-net ships

### 1. Tag each frame on the wire with its sender

`Wire` now stores `(Packet, sender_name)` frames, where `sender_name`
is the originating interface's name:

```python
wire.Put(packet, Sender="alice/eth0")
wire.Frames()      # -> [(Packet(...), 'alice/eth0'), ...]
wire.Consume(frame)
```

### 2. Split `Interface.Tick()` into two phases

```python
def FlushTx(self):
    # TX queue -> wire, tagged with self.Name
    ...

def DrainRx(self):
    # wire -> RX queue, skipping frames where sender == self.Name
    ...

def Tick(self):
    self.FlushTx()
    self.DrainRx()
```

### 3. Have `Internet.Tick()` drive the world in two passes

```python
for wire in wires: wire.Tick()
for node in nodes: node.FlushTx()      # everyone transmits first
for node in nodes: node.DrainRx()      # then everyone reads
```

Result: same-tick bidirectional delivery just works.

```text
ctrl@world> send alice "hi" bob 1
ctrl@world> send bob   "yo" alice 1
ctrl@world> tick
ctrl@world> drain alice          # -> "yo"
ctrl@world> drain bob            # -> "hi"
```

## Why the two-phase split matters

If you skip phase 2 and tick each node fully in turn:

```text
alice.Tick():   flush "hi" onto wire -> drain wire (only own packet, skip)
bob.Tick():     flush "yo" onto wire -> drain wire (sees "hi", takes it)
                                                      ^
                                                      | "yo" never reaches alice
                                                      | this tick — she already
                                                      | finished
```

Splitting the tick globally — "all transmits, then all reads" — eliminates
that asymmetry. It's the same trick used by ns-3, OMNeT++, and any other
serious discrete-event network simulator.

## Stretch goals

Now that point-to-point full-duplex works, here are real protocol-design
problems to dig into:

- **Multi-hop routing.** Add a third node with two interfaces. Have its
  `Tick()` forward packets from one interface to another based on
  `Packet.Dst`. Congratulations, you've built a router.
- **Addressing.** Decide what `Src` and `Dst` actually mean. Try MAC-style
  flat names, or hierarchical IP-style.
- **Propagation delay.** Make `Wire.Tick()` advance an internal counter
  so packets only become readable N ticks after being put on the wire.
  Each wire becomes a pipeline rather than an instantaneous buffer.
- **Loss.** Drop packets at random in `Wire.Put()` to simulate a lossy
  link, then design a small protocol that recovers using `Packet.Seq`.
- **Bandwidth.** Limit how many packets a wire can carry per tick, and
  see queues build up under congestion.
- **Broadcast / collision.** Connect three interfaces to the same wire
  and decide what happens when two transmit in the same tick.

Each of these is a real concept from networking, and each one is a small
patch to the same six files.
