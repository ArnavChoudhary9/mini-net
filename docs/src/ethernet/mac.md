# MAC Addresses

A **MAC address** is a 48-bit identifier assigned to a network interface
at the Ethernet layer. In mini-net they are plain lowercase strings of
the form `xx:xx:xx:xx:xx:xx`, so they slot directly into `Packet.Src`
and `Packet.Dst` without any conversion.

```python
from network import MAC

MAC.Random()                       # 'a3:f7:1c:09:42:bd'
MAC.IsValid("aa:bb:cc:dd:ee:ff")   # True
MAC.IsBroadcast(MAC.BROADCAST)     # True
MAC.BROADCAST                      # 'ff:ff:ff:ff:ff:ff'
```

Source: [`network/ethernet.py`](https://github.com/)

## Why a namespace, not a class?

A `MAC` object would just wrap a string. Treating MACs as strings means:

- They go straight into `Packet.Src` / `Packet.Dst` (no conversion).
- They are trivially hashable / printable / comparable.
- The `MAC` namespace stays small: a generator, a validator, a broadcast
  check, and a constant.

## API

| Member                | What it does                                   |
| --------------------- | ---------------------------------------------- |
| `MAC.BROADCAST`       | The all-ones address `'ff:ff:ff:ff:ff:ff'`     |
| `MAC.Random()`        | Generate a random `xx:xx:xx:xx:xx:xx` string   |
| `MAC.IsValid(addr)`   | True if `addr` parses as a valid MAC           |
| `MAC.IsBroadcast(addr)` | True if `addr` equals the broadcast address  |

## What's next

A MAC alone is just a string. The thing that travels on the wire is an
[Ethernet Frame](./frame.md).
