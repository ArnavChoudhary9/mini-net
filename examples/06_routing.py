"""
06_routing.py - Multi-Hop IP Routing
======================================

A linear chain of routers connects two hosts across three intermediate
subnets:

    alice          R1             R2             R3            bob
   .1.1/24 ---- .1.254/24 ---- .12.2/24 ---- .23.2/24 ---- .4.1/24
                .12.1/24       .23.1/24       .4.254/24

Each router has two interfaces and a small routing table. We watch:

  - a packet traverse all three routers (TTL decremented at each hop)
  - a low-TTL packet expire mid-route
  - a packet to an unknown subnet dropped with "no route"
"""

import logging
from network import Internet, Controller, IPInterface, Router
from network.log import EnableLogging

EnableLogging(logging.INFO)

# ── Topology ─────────────────────────────────────────────────────────────────

world = Internet("internet")

alice = world.AddNode("alice")
bob   = world.AddNode("bob")
r1    = world.AddNode("r1", Cls=Router)
r2    = world.AddNode("r2", Cls=Router)
r3    = world.AddNode("r3", Cls=Router)

# Wires (point-to-point links)
w_alice_r1 = world.AddWire("w_alice_r1")
w_r1_r2    = world.AddWire("w_r1_r2")
w_r2_r3    = world.AddWire("w_r2_r3")
w_r3_bob   = world.AddWire("w_r3_bob")

# Hosts
alice_eth = alice.AddInterface("eth0", Cls=IPInterface, Ip="10.0.1.1", PrefixLen=24)
alice_eth.Connect(w_alice_r1)

bob_eth = bob.AddInterface("eth0", Cls=IPInterface, Ip="10.0.4.1", PrefixLen=24)
bob_eth.Connect(w_r3_bob)

# r1: port0 toward alice (10.0.1.0/24), port1 toward r2 (10.0.12.0/24)
r1.AddInterface("eth0", Cls=IPInterface, Ip="10.0.1.254",  PrefixLen=24).Connect(w_alice_r1)
r1.AddInterface("eth1", Cls=IPInterface, Ip="10.0.12.1",   PrefixLen=24).Connect(w_r1_r2)

# r2: port0 toward r1, port1 toward r3 (10.0.23.0/24)
r2.AddInterface("eth0", Cls=IPInterface, Ip="10.0.12.2",   PrefixLen=24).Connect(w_r1_r2)
r2.AddInterface("eth1", Cls=IPInterface, Ip="10.0.23.1",   PrefixLen=24).Connect(w_r2_r3)

# r3: port0 toward r2, port1 toward bob (10.0.4.0/24)
r3.AddInterface("eth0", Cls=IPInterface, Ip="10.0.23.2",   PrefixLen=24).Connect(w_r2_r3)
r3.AddInterface("eth1", Cls=IPInterface, Ip="10.0.4.254",  PrefixLen=24).Connect(w_r3_bob)

# ── Routing tables ───────────────────────────────────────────────────────────

# r1 knows alice's LAN directly; everything else goes east toward r2
r1.AddRoute("10.0.1.0/24", IfaceIndex=0)
r1.AddRoute("0.0.0.0/0",   IfaceIndex=1, NextHop="10.0.12.2")

# r2 sits in the middle — west to alice's LAN via r1, east to everything else
r2.AddRoute("10.0.1.0/24", IfaceIndex=0, NextHop="10.0.12.1")
r2.AddRoute("0.0.0.0/0",   IfaceIndex=1, NextHop="10.0.23.2")

# r3 knows bob's LAN directly and how to reach alice's LAN via r2.
# Deliberately NO default route here, so anything else gets dropped.
r3.AddRoute("10.0.4.0/24", IfaceIndex=1)
r3.AddRoute("10.0.1.0/24", IfaceIndex=0, NextHop="10.0.23.1")

ctrl = Controller(world)

# ── Scenarios ────────────────────────────────────────────────────────────────

print("\n######## STEP 1 - alice -> bob (default TTL 64) ########")
alice_eth.SendIp(DstIp=bob_eth.Ip, Data=b"Hello, Bob!", Seq=1)
ctrl.Tick(4, ShowState=False)   # 4 hops: alice -> r1 -> r2 -> r3 -> bob
ctrl.Drain("bob")

print("\n######## STEP 2 - bob -> alice (reply) ########")
bob_eth.SendIp(DstIp=alice_eth.Ip, Data=b"Hi Alice!", Seq=1)
ctrl.Tick(4, ShowState=False)
ctrl.Drain("alice")

print("\n######## STEP 3 - TTL=2 (expires at r2) ########")
alice_eth.SendIp(DstIp=bob_eth.Ip, Data=b"short trip", Seq=2, TTL=2)
ctrl.Tick(4, ShowState=False)
ctrl.Drain("bob")    # should be empty

print("\n######## STEP 4 - TTL=4 (just enough to reach bob) ########")
alice_eth.SendIp(DstIp=bob_eth.Ip, Data=b"just made it", Seq=3, TTL=4)
ctrl.Tick(4, ShowState=False)
ctrl.Drain("bob")

print("\n######## STEP 5 - no route at r3 (no default there) ########")
alice_eth.SendIp(DstIp="99.99.99.99", Data=b"into the void", Seq=4)
ctrl.Tick(4, ShowState=False)
ctrl.Drain("bob")    # empty; r1 and r2 forward via default, r3 drops with "no route"

print("\n######## Routing tables ########")
for R in [r1, r2, r3]:
    print(f"  {R.Name}:")
    for Route_ in R.Routes:
        print(f"    {Route_}")
