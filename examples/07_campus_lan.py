"""
07_campus_lan.py - A Large Network with ARP, ICMP, and NAT
============================================================

Two LANs connected by a router that does source-NAT at the edge:

    Private LAN  10.0.1.0/24                  Public LAN  8.8.8.0/24
       alice 10.0.1.1                            server 8.8.8.8
       bob   10.0.1.2                                  |
       charlie 10.0.1.3                            [sw_b]
            |                                          |
        [sw_a]                                     r2 (8.8.8.254 + 203.0.113.2)
            |                                          |
        r1 (10.0.1.254 + 203.0.113.1 NAT) ── inter-router link (203.0.113.0/30)

What you'll see:

  Step 1 — alice pings bob (same LAN): ARP resolves alice<->bob MACs on sw_a,
           ICMP echo round-trips, no router involvement.

  Step 2 — alice pings server (different LAN through NAT):
           - alice ARPs for her gateway (r1) on the private side
           - r1 NATs the src 10.0.1.1 -> 203.0.113.1
           - r1 ARPs for r2 across the inter-router link
           - r2 ARPs for server on the public side
           - server replies to 203.0.113.1
           - r1 reverses NAT and delivers to alice
           Server only ever sees the router's public IP — exactly like
           your home network behind your ISP.

  Step 3 — bob pings server: r1 already has all the ARP entries cached,
           so this round-trip is much faster.

  Step 4 — alice traceroute-style: with TTL=1 r1 sends back ICMP Time
           Exceeded; bumping TTL reveals more of the path. This is how
           traceroute works.
"""

import logging
from network import (
    Internet, Controller, Switch, EthernetIPInterface, NatRouter, Router,
)
from network.icmp import EchoRequest
from network.log import EnableLogging

EnableLogging(logging.WARNING)   # quiet by default; flip to INFO for the trace

# ── Build the topology ───────────────────────────────────────────────────────

world = Internet("campus")

alice   = world.AddNode("alice")
bob     = world.AddNode("bob")
charlie = world.AddNode("charlie")
server  = world.AddNode("server")
sw_a    = world.AddNode("sw_a", Cls=Switch, Ports=4)
sw_b    = world.AddNode("sw_b", Cls=Switch, Ports=2)
r1      = world.AddNode("r1",   Cls=NatRouter)
r2      = world.AddNode("r2",   Cls=Router)

# Wires for LAN A
wa1 = world.AddWire("wa1");  wa2 = world.AddWire("wa2")
wa3 = world.AddWire("wa3");  wa4 = world.AddWire("wa4")
# Inter-router
wrr = world.AddWire("wrr")
# Wires for LAN B
wb1 = world.AddWire("wb1");  wb2 = world.AddWire("wb2")

# Private LAN hosts
alice_eth = alice.AddInterface(
    "eth0", Cls=EthernetIPInterface,
    Mac="aa:00:00:00:00:01", Ip="10.0.1.1",
    PrefixLen=24, Gateway="10.0.1.254")
alice_eth.Connect(wa1)

bob_eth = bob.AddInterface(
    "eth0", Cls=EthernetIPInterface,
    Mac="aa:00:00:00:00:02", Ip="10.0.1.2",
    PrefixLen=24, Gateway="10.0.1.254")
bob_eth.Connect(wa2)

charlie_eth = charlie.AddInterface(
    "eth0", Cls=EthernetIPInterface,
    Mac="aa:00:00:00:00:03", Ip="10.0.1.3",
    PrefixLen=24, Gateway="10.0.1.254")
charlie_eth.Connect(wa3)

# Switch A connects all three hosts plus r1
sw_a.Interfaces[0].Connect(wa1)
sw_a.Interfaces[1].Connect(wa2)
sw_a.Interfaces[2].Connect(wa3)
sw_a.Interfaces[3].Connect(wa4)

# Edge router r1 — private side on LAN A, public side on the inter-router link
r1.AddInterface("eth0", Cls=EthernetIPInterface,
                Mac="ee:01:00:00:00:01", Ip="10.0.1.254",
                PrefixLen=24).Connect(wa4)
r1.AddInterface("eth1", Cls=EthernetIPInterface,
                Mac="ee:01:00:00:00:02", Ip="203.0.113.1",
                PrefixLen=30, Gateway="203.0.113.2").Connect(wrr)
r1.AddRoute("10.0.1.0/24",    IfaceIndex=0)
r1.AddRoute("203.0.113.0/30", IfaceIndex=1)
r1.AddRoute("0.0.0.0/0",      IfaceIndex=1, NextHop="203.0.113.2")
r1.SetPrivateSide(0)
r1.SetPublicSide(1, "203.0.113.1")

# Plain router r2 — between r1's public side and the server's LAN
r2.AddInterface("eth0", Cls=EthernetIPInterface,
                Mac="ee:02:00:00:00:01", Ip="203.0.113.2",
                PrefixLen=30).Connect(wrr)
r2.AddInterface("eth1", Cls=EthernetIPInterface,
                Mac="ee:02:00:00:00:02", Ip="8.8.8.254",
                PrefixLen=24).Connect(wb1)
r2.AddRoute("203.0.113.0/30", IfaceIndex=0)
r2.AddRoute("8.8.8.0/24",     IfaceIndex=1)
r2.AddRoute("0.0.0.0/0",      IfaceIndex=0, NextHop="203.0.113.1")

# Public-side server + its switch
server_eth = server.AddInterface(
    "eth0", Cls=EthernetIPInterface,
    Mac="bb:00:00:00:00:01", Ip="8.8.8.8",
    PrefixLen=24, Gateway="8.8.8.254")
server_eth.Connect(wb2)
sw_b.Interfaces[0].Connect(wb1)
sw_b.Interfaces[1].Connect(wb2)

ctrl = Controller(world)


def Ping(Iface, DstIp, Seq, TTL=64):
    Iface.SendIpPacket(EchoRequest(
        Src=Iface.Ip, Dst=DstIp, SeqNumber=Seq, Data=b"ping", TTL=TTL,
    ))


# ── Step 1: same-LAN ping ────────────────────────────────────────────────────

print("\n######## STEP 1 - alice pings bob (same LAN, ARP via switch) ########")
Ping(alice_eth, bob_eth.Ip, Seq=1)
ctrl.Tick(10, ShowState=False)
ctrl.Drain("alice")
ctrl.Drain("bob")     # also drain bob — auto-reply leaves the echo-request in his queue
print(f"  alice ARP: {alice_eth.ArpCache}")


# ── Step 2: NAT'd cross-LAN ping ─────────────────────────────────────────────

print("\n######## STEP 2 - alice pings server (NAT + multi-hop) ########")
Ping(alice_eth, server_eth.Ip, Seq=1)
ctrl.Tick(25, ShowState=False)
ctrl.Drain("alice")
print(f"  r1 NAT table:")
for E in r1.NatTable:
    print(f"    {E.PrivateIp} <-> {E.PublicIp}  peer={E.DstIp}  id={E.Identifier}")


# ── Step 3: bob pings server (ARP cached, faster) ───────────────────────────

print("\n######## STEP 3 - bob pings server (router ARP already cached) ########")
Ping(bob_eth, server_eth.Ip, Seq=1)
ctrl.Tick(20, ShowState=False)
ctrl.Drain("bob")


# ── Step 4: traceroute via TTL ───────────────────────────────────────────────

print("\n######## STEP 4 - traceroute alice -> server (TTL=1, 2, 3) ########")
for ttl in (1, 2, 3):
    print(f"  -- TTL={ttl} --")
    Ping(alice_eth, server_eth.Ip, Seq=ttl + 10, TTL=ttl)
    ctrl.Tick(15, ShowState=False)
    ctrl.Drain("alice")
