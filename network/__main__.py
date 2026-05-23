"""
Entry point for `python -m network`.

Builds a small world and drops you into the interactive Controller REPL.
Pick a topology with a positional argument:

    python -m network                # default: 'basic' (2 nodes, 1 wire)
    python -m network basic          # alice + bob + one shared wire
    python -m network ethernet       # 3 hosts + 4-port learning switch
    python -m network lossy          # 2 nodes on a 30% lossy wire

This is the same Controller used inside the example scripts — it just
saves you from writing the topology by hand when you want to poke around.
"""

import argparse
import sys
from typing import Optional

from .internet import Internet
from .controller import Controller
from .ethernet import EthernetInterface, Switch


# ── topology builders ────────────────────────────────────────────────────────

def BuildBasic() -> Internet:
    """alice <-- wire --> bob"""
    World = Internet("world")
    Alice = World.AddNode("alice")
    Bob = World.AddNode("bob")
    Link = World.AddWire("link")
    Alice.AddInterface("eth0").Connect(Link)
    Bob.AddInterface("eth0").Connect(Link)
    return World


def BuildEthernet() -> Internet:
    """3 hosts behind a 4-port learning switch."""
    World = Internet("lan")

    Alice = World.AddNode("alice")
    Bob = World.AddNode("bob")
    Charlie = World.AddNode("charlie")
    Sw = World.AddNode("sw", Cls=Switch, Ports=4)

    Wa = World.AddWire("wa")
    Wb = World.AddWire("wb")
    Wc = World.AddWire("wc")

    Alice.AddInterface("eth0", Cls=EthernetInterface,
                       Mac="aa:aa:aa:aa:aa:aa").Connect(Wa)
    Bob.AddInterface("eth0", Cls=EthernetInterface,
                     Mac="bb:bb:bb:bb:bb:bb").Connect(Wb)
    Charlie.AddInterface("eth0", Cls=EthernetInterface,
                         Mac="cc:cc:cc:cc:cc:cc").Connect(Wc)

    Sw.Interfaces[0].Connect(Wa)
    Sw.Interfaces[1].Connect(Wb)
    Sw.Interfaces[2].Connect(Wc)

    return World


def BuildLossy() -> Internet:
    """alice <-- 30% lossy wire --> bob.  Send many packets to see drops."""
    World = Internet("world")
    Alice = World.AddNode("alice")
    Bob = World.AddNode("bob")
    Link = World.AddWire("flaky", DropRate=0.3)
    Alice.AddInterface("eth0").Connect(Link)
    Bob.AddInterface("eth0").Connect(Link)
    return World


TOPOLOGIES = {
    "basic":    BuildBasic,
    "ethernet": BuildEthernet,
    "lossy":    BuildLossy,
}


# ── entry point ──────────────────────────────────────────────────────────────

def Main(Argv: Optional[list[str]] = None) -> int:
    Parser = argparse.ArgumentParser(
        prog="python -m network",
        description="Build a small mini-net world and launch the Controller REPL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
topologies:
  basic     (default) two nodes connected by one wire
  ethernet  three hosts + a 4-port learning switch
  lossy     two nodes on a 30% lossy wire

inside the REPL, type 'help' for available commands.
""",
    )
    Parser.add_argument(
        "topology", nargs="?", default="basic",
        choices=sorted(TOPOLOGIES.keys()),
        help="which topology to build (default: basic)",
    )
    Args = Parser.parse_args(Argv)

    World = TOPOLOGIES[Args.topology]()
    Controller(World).Repl()
    return 0


if __name__ == "__main__":
    sys.exit(Main())
