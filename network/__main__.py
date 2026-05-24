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
from .ip import IPInterface, Router
from .arp import EthernetIPInterface
from .nat import NatRouter
from .routing import DynamicRouter


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


def BuildRouted() -> Internet:
    """alice -- r1 -- r2 -- r3 -- bob.  Three-router chain for IP routing."""
    World = Internet("internet")

    Alice = World.AddNode("alice")
    Bob = World.AddNode("bob")
    R1 = World.AddNode("r1", Cls=Router)
    R2 = World.AddNode("r2", Cls=Router)
    R3 = World.AddNode("r3", Cls=Router)

    Wa  = World.AddWire("w_alice_r1")
    W12 = World.AddWire("w_r1_r2")
    W23 = World.AddWire("w_r2_r3")
    Wb  = World.AddWire("w_r3_bob")

    Alice.AddInterface("eth0", Cls=IPInterface, Ip="10.0.1.1",   PrefixLen=24).Connect(Wa)
    Bob.AddInterface(  "eth0", Cls=IPInterface, Ip="10.0.4.1",   PrefixLen=24).Connect(Wb)

    R1.AddInterface("eth0", Cls=IPInterface, Ip="10.0.1.254",  PrefixLen=24).Connect(Wa)
    R1.AddInterface("eth1", Cls=IPInterface, Ip="10.0.12.1",   PrefixLen=24).Connect(W12)

    R2.AddInterface("eth0", Cls=IPInterface, Ip="10.0.12.2",   PrefixLen=24).Connect(W12)
    R2.AddInterface("eth1", Cls=IPInterface, Ip="10.0.23.1",   PrefixLen=24).Connect(W23)

    R3.AddInterface("eth0", Cls=IPInterface, Ip="10.0.23.2",   PrefixLen=24).Connect(W23)
    R3.AddInterface("eth1", Cls=IPInterface, Ip="10.0.4.254",  PrefixLen=24).Connect(Wb)

    R1.AddRoute("10.0.1.0/24", IfaceIndex=0)
    R1.AddRoute("0.0.0.0/0",   IfaceIndex=1, NextHop="10.0.12.2")

    R2.AddRoute("10.0.1.0/24", IfaceIndex=0, NextHop="10.0.12.1")
    R2.AddRoute("0.0.0.0/0",   IfaceIndex=1, NextHop="10.0.23.2")

    R3.AddRoute("10.0.4.0/24", IfaceIndex=1)
    R3.AddRoute("10.0.1.0/24", IfaceIndex=0, NextHop="10.0.23.1")

    return World


def BuildCampus() -> Internet:
    r"""
    Two LANs, each behind a switch and a router. The two routers share
    a point-to-point link. The left router does NAT — alice/bob/charlie
    use private 10.0.1.0/24 addresses but appear as 203.0.113.1 (the
    router's public IP) from the server's perspective.

        10.0.1.0/24                 203.0.113.0/30           8.8.8.0/24
        alice  bob  charlie                                   server
          \   |   /                                              |
          [switch_a]                                        [switch_b]
              |                                                  |
        r1 (10.0.1.254 + 203.0.113.1 NAT) ──link── r2 (203.0.113.2 + 8.8.8.254)
    """
    World = Internet("campus")

    # Private LAN hosts
    Alice = World.AddNode("alice")
    Bob = World.AddNode("bob")
    Charlie = World.AddNode("charlie")

    # Public LAN host
    Server = World.AddNode("server")

    # Switches
    SwA = World.AddNode("sw_a", Cls=Switch, Ports=4)
    SwB = World.AddNode("sw_b", Cls=Switch, Ports=2)

    # Routers (r1 does NAT, r2 is plain)
    R1 = World.AddNode("r1", Cls=NatRouter)
    R2 = World.AddNode("r2", Cls=Router)

    # Wires for LAN A
    Wa1 = World.AddWire("wa1");   Wa2 = World.AddWire("wa2")
    Wa3 = World.AddWire("wa3");   Wa4 = World.AddWire("wa4")
    # Wire for inter-router link
    WrR = World.AddWire("wrr")
    # Wires for LAN B
    Wb1 = World.AddWire("wb1");   Wb2 = World.AddWire("wb2")

    # LAN A hosts (private 10.0.1.0/24, gateway = r1's private IP)
    Alice.AddInterface("eth0", Cls=EthernetIPInterface,
                       Mac="aa:00:00:00:00:01", Ip="10.0.1.1",
                       PrefixLen=24, Gateway="10.0.1.254").Connect(Wa1)
    Bob.AddInterface("eth0", Cls=EthernetIPInterface,
                     Mac="aa:00:00:00:00:02", Ip="10.0.1.2",
                     PrefixLen=24, Gateway="10.0.1.254").Connect(Wa2)
    Charlie.AddInterface("eth0", Cls=EthernetIPInterface,
                         Mac="aa:00:00:00:00:03", Ip="10.0.1.3",
                         PrefixLen=24, Gateway="10.0.1.254").Connect(Wa3)

    # Switch A connects all three hosts and r1
    SwA.Interfaces[0].Connect(Wa1)
    SwA.Interfaces[1].Connect(Wa2)
    SwA.Interfaces[2].Connect(Wa3)
    SwA.Interfaces[3].Connect(Wa4)

    # r1: private side on Wa4 (LAN A), public side on WrR (inter-router link)
    R1.AddInterface("eth0", Cls=EthernetIPInterface,
                    Mac="ee:01:00:00:00:01", Ip="10.0.1.254",
                    PrefixLen=24).Connect(Wa4)
    R1.AddInterface("eth1", Cls=EthernetIPInterface,
                    Mac="ee:01:00:00:00:02", Ip="203.0.113.1",
                    PrefixLen=30, Gateway="203.0.113.2").Connect(WrR)
    R1.AddRoute("10.0.1.0/24",    IfaceIndex=0)
    R1.AddRoute("203.0.113.0/30", IfaceIndex=1)
    R1.AddRoute("0.0.0.0/0",      IfaceIndex=1, NextHop="203.0.113.2")
    R1.SetPrivateSide(0)
    R1.SetPublicSide(1, "203.0.113.1")

    # r2: public-side toward r1 on WrR, server-side on Wb1
    R2.AddInterface("eth0", Cls=EthernetIPInterface,
                    Mac="ee:02:00:00:00:01", Ip="203.0.113.2",
                    PrefixLen=30).Connect(WrR)
    R2.AddInterface("eth1", Cls=EthernetIPInterface,
                    Mac="ee:02:00:00:00:02", Ip="8.8.8.254",
                    PrefixLen=24).Connect(Wb1)
    R2.AddRoute("203.0.113.0/30", IfaceIndex=0)
    R2.AddRoute("8.8.8.0/24",     IfaceIndex=1)
    R2.AddRoute("0.0.0.0/0",      IfaceIndex=0, NextHop="203.0.113.1")

    # LAN B: server + switch
    Server.AddInterface("eth0", Cls=EthernetIPInterface,
                        Mac="bb:00:00:00:00:01", Ip="8.8.8.8",
                        PrefixLen=24, Gateway="8.8.8.254").Connect(Wb2)
    SwB.Interfaces[0].Connect(Wb1)
    SwB.Interfaces[1].Connect(Wb2)

    return World


def BuildDynamic() -> Internet:
    r"""
    Three DynamicRouters in a triangle. Each one starts with only its
    connected routes; after a few rounds of advertisements, every
    router knows how to reach every subnet.

           alice (10.0.1.1)                bob (10.0.2.1)
              \                                /
               r1 (10.0.1.254) ── link ── r2 (10.0.2.254)
                10.0.12.0/30                10.0.12.0/30
                       \                /
                        \              /
                       10.0.13.0/30  10.0.23.0/30
                          r3 (10.0.3.254)
                             |
                          charlie (10.0.3.1)
    """
    World = Internet("dyn")

    Alice = World.AddNode("alice")
    Bob = World.AddNode("bob")
    Charlie = World.AddNode("charlie")
    R1 = World.AddNode("r1", Cls=DynamicRouter, AdvertiseInterval=3)
    R2 = World.AddNode("r2", Cls=DynamicRouter, AdvertiseInterval=3)
    R3 = World.AddNode("r3", Cls=DynamicRouter, AdvertiseInterval=3)

    Wa = World.AddWire("wa");  Wb = World.AddWire("wb");  Wc = World.AddWire("wc")
    W12 = World.AddWire("w12"); W13 = World.AddWire("w13"); W23 = World.AddWire("w23")

    Alice.AddInterface("eth0", Cls=EthernetIPInterface,
                       Mac="aa:00:00:00:00:01", Ip="10.0.1.1",
                       PrefixLen=24, Gateway="10.0.1.254").Connect(Wa)
    Bob.AddInterface("eth0", Cls=EthernetIPInterface,
                     Mac="bb:00:00:00:00:01", Ip="10.0.2.1",
                     PrefixLen=24, Gateway="10.0.2.254").Connect(Wb)
    Charlie.AddInterface("eth0", Cls=EthernetIPInterface,
                         Mac="cc:00:00:00:00:01", Ip="10.0.3.1",
                         PrefixLen=24, Gateway="10.0.3.254").Connect(Wc)

    R1.AddInterface("eth0", Cls=EthernetIPInterface, Mac="e1:00:00:00:00:01",
                    Ip="10.0.1.254", PrefixLen=24).Connect(Wa)
    R1.AddInterface("eth1", Cls=EthernetIPInterface, Mac="e1:00:00:00:00:02",
                    Ip="10.0.12.1",  PrefixLen=30).Connect(W12)
    R1.AddInterface("eth2", Cls=EthernetIPInterface, Mac="e1:00:00:00:00:03",
                    Ip="10.0.13.1",  PrefixLen=30).Connect(W13)

    R2.AddInterface("eth0", Cls=EthernetIPInterface, Mac="e2:00:00:00:00:01",
                    Ip="10.0.2.254", PrefixLen=24).Connect(Wb)
    R2.AddInterface("eth1", Cls=EthernetIPInterface, Mac="e2:00:00:00:00:02",
                    Ip="10.0.12.2",  PrefixLen=30).Connect(W12)
    R2.AddInterface("eth2", Cls=EthernetIPInterface, Mac="e2:00:00:00:00:03",
                    Ip="10.0.23.1",  PrefixLen=30).Connect(W23)

    R3.AddInterface("eth0", Cls=EthernetIPInterface, Mac="e3:00:00:00:00:01",
                    Ip="10.0.3.254", PrefixLen=24).Connect(Wc)
    R3.AddInterface("eth1", Cls=EthernetIPInterface, Mac="e3:00:00:00:00:02",
                    Ip="10.0.13.2",  PrefixLen=30).Connect(W13)
    R3.AddInterface("eth2", Cls=EthernetIPInterface, Mac="e3:00:00:00:00:03",
                    Ip="10.0.23.2",  PrefixLen=30).Connect(W23)

    # Seed each router with its connected subnets — advertisements
    # will fill in the rest.
    for R in (R1, R2, R3):
        R.InstallConnectedRoutes()

    return World


TOPOLOGIES = {
    "basic":    BuildBasic,
    "ethernet": BuildEthernet,
    "lossy":    BuildLossy,
    "routed":   BuildRouted,
    "campus":   BuildCampus,
    "dynamic":  BuildDynamic,
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
  routed    alice -- r1 -- r2 -- r3 -- bob  (multi-hop IP routing)

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
