# Ethernet Frames

An `EthernetFrame` is a `Packet` with an extra `EtherType` field. It is
what really travels across an Ethernet link.

```python
@dataclass(frozen=True)
class EthernetFrame(Packet):
    EtherType: int = 0x0800   # IPv4 by default
    # inherits Data, Src, Dst, Seq from Packet
```

Source: [`network/ethernet.py`](https://github.com/)

## Real Ethernet vs. mini-net's frame

A real Ethernet frame on the wire looks roughly like:

```text
+------+------+--------+----------------+-----+
| DST  | SRC  | TYPE   | PAYLOAD        | CRC |
| 6 B  | 6 B  | 2 B    | up to 1500 B   | 4 B |
+------+------+--------+----------------+-----+
```

mini-net drops the CRC (it cannot be corrupted in a Python simulation
without us inventing the corruption) but keeps the four meaningful
fields:

| Real Ethernet   | mini-net field |
| --------------- | -------------- |
| Destination MAC | `Dst`          |
| Source MAC      | `Src`          |
| EtherType       | `EtherType`    |
| Payload         | `Data`         |

`Seq` is mini-net's addition — handy when you are writing higher-level
protocols on top.

## Why subclass Packet?

`EthernetFrame` *is* a `Packet`. That means:

- It travels through a `Wire` and an `Interface` with no special handling.
- A non-Ethernet `Switch` that only inspected `Packet.Dst` would still
  work on frames (because `Dst` is just a string).
- You can mix raw packets and frames on the same wire during testing.

## Common EtherTypes

| Value     | Protocol  | Notes                                  |
| --------- | --------- | -------------------------------------- |
| `0x0800`  | IPv4      | The default in mini-net                |
| `0x0806`  | ARP       | Address resolution                     |
| `0x86dd`  | IPv6      |                                        |
| `0x88cc`  | LLDP      | Link-layer discovery                   |

mini-net does not interpret `EtherType` — it is your hook for adding
higher-layer demultiplexing when you build a network stack on top.

## Example

```python
from network import EthernetFrame

frame = EthernetFrame(
    Data=b"hello",
    Src="aa:aa:aa:aa:aa:aa",
    Dst="bb:bb:bb:bb:bb:bb",
    Seq=1,
)
print(frame)
# Frame(EtherType=0x0800, Src='aa:aa:aa:aa:aa:aa', Dst='bb:bb:bb:bb:bb:bb', Seq=1, Data=b'hello')
```

You rarely construct frames by hand — use
[`EthernetInterface.SendFrame()`](./interface.md) which fills in `Src`
from the interface's MAC.
