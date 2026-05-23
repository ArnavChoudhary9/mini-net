# Getting Started

## Install

mini-net requires **Python 3.9+** and has no runtime dependencies.

```bash
git clone <repo>
cd mini-net
pip install -e .
```

The `-e` installs in editable mode so any change you make to `network/`
takes effect immediately.

## Quickest path: `python -m network`

For ad-hoc exploration, skip the example files and launch the REPL
directly with a prebuilt topology:

```bash
python -m network                  # 2 nodes + 1 wire (default)
python -m network ethernet         # 3 hosts + 4-port learning switch
python -m network lossy            # 2 nodes on a 30% lossy wire
python -m network --help           # list available topologies
```

You'll land at a prompt:

```text
ctrl@lan> mactable sw
ctrl@lan> frame alice bb:bb:bb:bb:bb:bb "ping" 1
ctrl@lan> tick 2
ctrl@lan> drain bob
```

## Run the examples

Five walkthrough scripts, in order of increasing depth:

```bash
python examples/01_foundation.py     # the four building blocks
python examples/02_controller.py     # programmatic debugger
python examples/03_repl.py           # interactive console
python examples/04_ethernet.py       # MAC, frames, switch (scripted)
python examples/05_ethernet_repl.py  # switched LAN (interactive)
```

Each example is fully self-contained. Read through the source — they
are written as much for reading as for running.

## A 30-second sanity check

```python
from network import Internet, Controller

world = Internet("hello")
alice = world.AddNode("alice")
bob   = world.AddNode("bob")
link  = world.AddWire("link")

alice.AddInterface("eth0").Connect(link)
bob.AddInterface("eth0").Connect(link)

ctrl = Controller(world)
ctrl.Send("alice", b"hi", Dst="bob")
ctrl.Tick()
ctrl.Inspect()
```

Expected: a packet from alice will appear on the wire. It will **not** appear
in bob's RX queue yet — that requires the [duplex implementation](./duplex-challenge.md).

## Build the docs locally

```bash
cargo install mdbook
mdbook serve docs        # http://localhost:3000
mdbook build docs        # static HTML in docs/book/
```

You don't need mdbook to read the docs — the markdown files under
[`docs/src/`](../src/) are perfectly readable on their own.
