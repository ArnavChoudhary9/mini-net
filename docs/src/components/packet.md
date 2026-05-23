# Packet

The unit of data that travels across the network.

```python
@dataclass(frozen=True)
class Packet:
    Data: bytes
    Src:  str = ""
    Dst:  str = ""
    Seq:  int = 0
```

Source: [`network/packet.py`](https://github.com/)

## Why frozen?

A `Packet` is immutable. Once you create one, its fields can't change. This
is deliberate:

- **Realism.** Real packets are bytes on a wire. Whoever has them owns a
  copy; you can't reach back and mutate the sender's copy.
- **Safety.** Putting the same packet on two wires can't lead to one wire
  modifying what the other sees.

If you want to change a field, build a new `Packet`.

## Fields

| Field | Type    | Meaning                                                  |
| ----- | ------- | -------------------------------------------------------- |
| Data  | `bytes` | The payload — raw bytes, application-level                |
| Src   | `str`   | Who sent it (application-level address, set by you)      |
| Dst   | `str`   | Who it's for (application-level address, set by you)     |
| Seq   | `int`   | Sequence number — useful once you build reliable delivery |

`Src` and `Dst` are **strings you choose**. mini-net does not impose any
addressing scheme. You can use node names, IP-style addresses, or whatever
matches the lesson you're working on.

## Example

```python
from network import Packet

pkt = Packet(Data=b"Hello!", Src="alice", Dst="bob", Seq=1)
print(pkt)
# Packet(Seq=1, Src='alice', Dst='bob', Data=b'Hello!')
```

## What's next

A packet by itself is just a value. It has to travel over a [Wire](./wire.md).
