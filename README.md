# mini-net

A tiny, hackable, tick-based network simulator for **learning how the internet
actually works** — one packet at a time.

```text
        +-------+                          +-------+
        | alice |-- eth0 -- wire -- eth0 --|  bob  |
        +-------+                          +-------+
```

You build a world (`Internet`) made of nodes and wires, send packets, advance
time one tick at a time, and watch every packet move through the system.

```python
from network import Internet, Controller

world = Internet("world")
alice = world.AddNode("alice")
bob   = world.AddNode("bob")
link  = world.AddWire("link")

alice.AddInterface("eth0").Connect(link)
bob.AddInterface("eth0").Connect(link)

ctrl = Controller(world)
ctrl.Repl()                # interactive console
```

```text
ctrl@world> send alice "Hello, Bob!" bob
ctrl@world> tick
ctrl@world> peek link
ctrl@world> drain bob
```

## Quick start

```bash
git clone <repo>
cd mini-net
pip install -e .

# fastest way to play — launches the REPL with a prebuilt topology
python -m network                    # 2 nodes + 1 wire
python -m network ethernet           # 3 hosts + 4-port learning switch
python -m network lossy              # 2 nodes on a 30% lossy wire
python -m network routed             # alice -- r1 -- r2 -- r3 -- bob
python -m network dynamic            # 3 DynamicRouters discover each other
python -m network campus             # full LAN: switches + NAT edge router

# or run the walkthroughs
python examples/01_foundation.py     # Packet -> Wire -> Interface -> Node
python examples/02_controller.py     # programmatic controller
python examples/03_repl.py           # interactive REPL, scripted setup
python examples/04_ethernet.py       # MAC, frames, a learning switch
python examples/05_ethernet_repl.py  # switched LAN, interactive
python examples/06_routing.py        # multi-hop IP routing + TTL
python examples/07_campus_lan.py     # ARP + ICMP + NAT + traceroute
python examples/08_udp.py            # UDP echo server with two clients
```

## What's inside

| Component               | What it models                                                   |
| ----------------------- | ---------------------------------------------------------------- |
| **Packet**              | The unit of data on the network (`Data`, `Src`, `Dst`, `Seq`)    |
| **Wire**                | A FIFO buffer — the physical medium (supports random `DropRate`) |
| **Interface**           | A port on a node with a TX queue and a connected wire            |
| **Node**                | A device (host, router) that owns one or more interfaces         |
| **Internet**            | The simulation world; ticks every wire and node in step          |
| **Controller**          | A debugger you can drive from code or an interactive REPL        |
| **MAC + EthernetFrame** | Layer-2 addressing and the frame that travels on the wire        |
| **EthernetInterface**   | An `Interface` with a MAC address and `SendFrame()` helper       |
| **Switch**              | A `Node` that learns MACs and forwards frames between ports      |
| **IP + IPPacket**       | Layer-3 dotted-quad addresses, CIDR subnets, packets with TTL    |
| **IPInterface**         | An `Interface` with an IP / subnet and `SendIp()` helper         |
| **Router**              | A `Node` that forwards IP packets by longest-prefix match + TTL  |
| **ARP**                 | Resolves IP → MAC via broadcast (used by `EthernetIPInterface`)  |
| **EthernetIPInterface** | Combined MAC + IP interface with an ARP cache + auto-ICMP-reply  |
| **ICMP**                | Ping (echo), Time Exceeded, Destination Unreachable              |
| **DynamicRouter**       | Distance-vector routing (RIP-style) — peers exchange routes      |
| **NatRouter**           | Source-NAT at the edge — many private IPs, one public IP         |
| **MTU + Fragmentation** | Wires have MTU; routers fragment; hosts reassemble               |
| **UDP + UdpSocket**     | Datagrams, ports, bind/send/receive, Port Unreachable ICMP       |

## Learning philosophy

The library is intentionally **incomplete**: `Interface.Tick()` only flushes
the TX queue — the **read side (duplex)** is left for you to implement.
The `Controller` is there so you can watch your implementation work
(or fail) in real time without writing custom plumbing.

See [docs/](docs/) for the full walkthrough, or jump straight to the
[duplex challenge](docs/src/duplex-challenge.md).

## Documentation

The full docs are written as an [mdbook](https://rust-lang.github.io/mdBook/):

```bash
cargo install mdbook
mdbook serve docs       # http://localhost:3000
```

You can also read the markdown files in [docs/src/](docs/src/) directly.

## Layout

```text
network/                core library
  packet.py             Packet
  wire.py               Wire (FIFO + optional DropRate)
  interface.py          Interface (FlushTx + DrainRx)
  node.py               Node
  internet.py           Internet (two-phase global tick)
  ethernet.py           MAC, EthernetFrame, EthernetInterface, Switch
  ip.py                 IP, IPPacket (TTL), IPInterface, Route, Router
  arp.py                ArpMessage + EthernetIPInterface (MAC+IP+ARP)
  icmp.py               IcmpMessage, echo / time-exceeded / unreachable
  udp.py                UdpDatagram + UdpSocket (BindUdp on the interface)
  routing.py            DynamicRouter — distance-vector convergence
  nat.py                NatRouter — source NAT at the edge
  frag.py               MTU, FragmentedIPPacket, Reassembler
  controller.py         Controller + REPL (ping, arp, routes, nat...)
  log.py                EnableLogging() / DisableLogging()
examples/
  01_foundation.py      building blocks bottom-up
  02_controller.py      programmatic debugger
  03_repl.py            interactive console (basic 2-node)
  04_ethernet.py        switched LAN with MAC learning (scripted)
  05_ethernet_repl.py   switched LAN (interactive)
  06_routing.py         5-node IP chain — multi-hop routing + TTL
  07_campus_lan.py      ARP + ICMP + NAT + traceroute (the full stack)
  08_udp.py             UDP datagrams + bound sockets + Port Unreachable
docs/                   mdbook site

python -m network [topology]    # quick REPL launch (see __main__.py)
```
