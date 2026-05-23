# Ethernet Interface

`EthernetInterface` extends [`Interface`](../components/interface.md) with
a MAC address and a `SendFrame()` helper. It is the L2-aware version of
a network port.

```python
class EthernetInterface(Interface):
    Mac: str                                # 'aa:bb:cc:dd:ee:ff'

    def SendFrame(self, DstMac, Payload, EtherType=0x0800, Seq=0) -> bool
    def ReceiveFrame(self) -> Optional[Packet]
```

Source: [`network/ethernet.py`](https://github.com/)

## Creating one

The cleanest way is via `Node.AddInterface()` with the `Cls=` kwarg:

```python
alice = world.AddNode("alice")
alice_eth = alice.AddInterface(
    "eth0",
    Cls=EthernetInterface,
    Mac="aa:aa:aa:aa:aa:aa",
)
```

If you omit `Mac`, a random one is generated:

```python
alice.AddInterface("eth0", Cls=EthernetInterface)
# Mac = something like '6f:32:0c:91:e4:a8'
```

## Sending frames

```python
alice_eth.SendFrame(
    DstMac="bb:bb:bb:bb:bb:bb",
    Payload=b"Hello, Bob!",
    Seq=1,
)
```

`SendFrame` builds an `EthernetFrame` with `Src` set to `self.Mac` and
queues it on the TX queue. It returns `False` only if no wire is
attached.

## Receiving frames

`ReceiveFrame()` is just a typed alias for `Receive()` — it pops the
next packet from the RX queue. The packet you get back is the
`EthernetFrame` someone else built and put on the wire.

```python
frame = bob_eth.ReceiveFrame()
if frame:
    print(f"from {frame.Src}: {frame.Data!r}")
```

## What's next

Two end hosts with EthernetInterfaces connected by one wire is already
a useful network. To wire up more than two devices you need a
[Switch](./switch.md).
