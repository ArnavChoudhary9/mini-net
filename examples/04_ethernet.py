"""
04_ethernet.py - A Switched Ethernet LAN
==========================================

Topology:

      alice ─── wire_a ─── [port0]
                           [port1] ─── wire_b ─── bob
                           [port2] ─── wire_c ─── charlie
                           [port3] (unused)
                              switch

Demonstrates:
  - MAC addresses
  - Ethernet frames built by EthernetInterface.SendFrame()
  - A learning Switch that builds its MAC table over time
  - Flooding when destination is unknown or broadcast
"""

import logging
from network import Internet, Controller, EthernetInterface, Switch, MAC
from network.log import EnableLogging

EnableLogging(logging.INFO)

# ── Build the LAN ────────────────────────────────────────────────────────────

world = Internet("lan")

alice   = world.AddNode("alice")
bob     = world.AddNode("bob")
charlie = world.AddNode("charlie")

alice_eth   = alice.AddInterface("eth0",
                                 Cls=EthernetInterface, Mac="aa:aa:aa:aa:aa:aa")
bob_eth     = bob.AddInterface("eth0",
                               Cls=EthernetInterface, Mac="bb:bb:bb:bb:bb:bb")
charlie_eth = charlie.AddInterface("eth0",
                                   Cls=EthernetInterface, Mac="cc:cc:cc:cc:cc:cc")

sw = world.AddNode("sw", Cls=Switch, Ports=4)

wire_a = world.AddWire("wire_a")
wire_b = world.AddWire("wire_b")
wire_c = world.AddWire("wire_c")

alice_eth.Connect(wire_a);    sw.Interfaces[0].Connect(wire_a)
bob_eth.Connect(wire_b);      sw.Interfaces[1].Connect(wire_b)
charlie_eth.Connect(wire_c);  sw.Interfaces[2].Connect(wire_c)

ctrl = Controller(world)

# ── Scenario 1: alice -> bob (switch doesn't know either yet) ────────────────

print("\n######## STEP 1 — Alice -> Bob (switch knows nobody) ########")
alice_eth.SendFrame(DstMac=bob_eth.Mac, Payload=b"Hello, Bob!", Seq=1)
ctrl.Tick(2, ShowState=False)
# After 2 ticks: alice -> switch (learn alice, flood) -> bob & charlie

ctrl.Drain("bob")
ctrl.Drain("charlie")
print(f"  switch MAC table: {sw.MacTable}")

# ── Scenario 2: bob -> alice (switch knows alice, learns bob) ────────────────

print("\n######## STEP 2 — Bob -> Alice (switch knows Alice, learns Bob) ########")
bob_eth.SendFrame(DstMac=alice_eth.Mac, Payload=b"Hi Alice!", Seq=1)
ctrl.Tick(2, ShowState=False)
# Switch knows alice on port0, so this is forwarded (not flooded)

ctrl.Drain("alice")
ctrl.Drain("charlie")     # charlie should NOT get this
print(f"  switch MAC table: {sw.MacTable}")

# ── Scenario 3: broadcast ─────────────────────────────────────────────────────

print("\n######## STEP 3 — Alice broadcasts ########")
alice_eth.SendFrame(DstMac=MAC.BROADCAST, Payload=b"ANYBODY HOME?", Seq=2)
ctrl.Tick(2, ShowState=False)

ctrl.Drain("bob")
ctrl.Drain("charlie")

# ── Scenario 4: alice -> bob again (now fully learned) ────────────────────────

print("\n######## STEP 4 — Alice -> Bob again (no flooding this time) ########")
alice_eth.SendFrame(DstMac=bob_eth.Mac, Payload=b"how about now?", Seq=3)
ctrl.Tick(2, ShowState=False)

ctrl.Drain("bob")
ctrl.Drain("charlie")     # charlie should NOT get this
print(f"  switch MAC table: {sw.MacTable}")
