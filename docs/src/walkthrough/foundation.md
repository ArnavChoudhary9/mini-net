# 01 — Foundation

> Source: [`examples/01_foundation.py`](https://github.com/)

A bottom-up tour of the four building blocks. Run it:

```bash
python examples/01_foundation.py
```

## Part 1 — Packet

The smallest unit. A `Packet` is a frozen dataclass that carries some
`Data` plus optional `Src`, `Dst`, `Seq` fields you set yourself.

```python
pkt = Packet(Data=b"Hello, network!", Src="alice", Dst="bob", Seq=1)
```

## Part 2 — Wire

A `Wire` is a FIFO buffer. Things go in with `Put`, come out with `Get`.

```python
wire = Wire(Name="alice->bob")
wire.Put(Packet(Data=b"first",  Src="alice", Seq=1))
wire.Put(Packet(Data=b"second", Src="alice", Seq=2))

wire.Get()        # Packet(... Data=b'first')
wire.Get()        # Packet(... Data=b'second')
```

## Part 3 — Interface

An `Interface` adds two queues around a wire: a TX queue (waiting to be
sent) and an RX queue (waiting to be read). `Tick()` currently flushes
the TX queue onto the wire.

```python
iface = Interface(Name="alice/eth0")
iface.Connect(wire)

iface.Send(Packet(Data=b"ping 1", Src="alice", Seq=1))
iface.Send(Packet(Data=b"ping 2", Src="alice", Seq=2))
iface.Tick()      # packets are now on the wire

print(wire.Get())  # Packet(... Data=b'ping 1')
print(wire.Get())  # Packet(... Data=b'ping 2')
```

## Part 4 — Node

A `Node` is a named bag of interfaces with a bulk `Tick()`.

```python
alice = Node("alice")
eth0  = alice.AddInterface("eth0")
eth0.Connect(Wire(Name="alice->bob"))

alice.Send(Packet(Data=b"Hello, Bob!", Src="alice", Dst="bob", Seq=1))
alice.Tick()
```

## Part 5 — Disconnected interface

When an interface has no wire attached, `Send()` returns `False` and the
packet is discarded. This is exactly what happens on a real network
when there's no cable.

```python
lonely = Node("lonely")
lonely.AddInterface("eth0")
ok = lonely.Send(Packet(Data=b"hello", Src="lonely"))
# ok == False
```

## Takeaways

- Wires are dumb buffers. The interface is what makes them useful.
- `Tick()` is the only thing that moves data between layers.
- Nothing reads the wire yet — that's the whole point of mini-net's design.
