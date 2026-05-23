"""
02_controller.py - Two Nodes, One Wire, Driven by a Controller
================================================================

Topology:

        +-------+                          +-------+
        | alice |-- eth0 -- wire -- eth0 --|  bob  |
        +-------+                          +-------+

Everything lives inside an Internet (the simulation world). A Controller
is wrapped around the Internet and lets you poke at any part of it:

    ctrl.Send("alice", b"hi", Dst="bob")   queue a packet on alice/eth0
    ctrl.Tick()                             advance the world one step
    ctrl.Inspect()                          print wires + interface queues
    ctrl.Drain("bob")                       read everything in bob's RX

With two-phase ticking (FlushTx on everyone, then DrainRx on everyone)
and a sender-tagged wire, both ends can communicate in a single tick.
"""

import logging
from network import Internet, Controller
from network.log import EnableLogging

EnableLogging(logging.WARNING)   # quiet by default; raise to DEBUG to see internals

# ── 1. Build the world ───────────────────────────────────────────────────────

world = Internet("world")

alice = world.AddNode("alice")
bob   = world.AddNode("bob")

link  = world.AddWire("link", Capacity=8)

alice_eth0 = alice.AddInterface("eth0")
bob_eth0   = bob.AddInterface("eth0")

# Both interfaces share the single wire.
alice_eth0.Connect(link)
bob_eth0.Connect(link)

# ── 2. Hand the world to a debugger ──────────────────────────────────────────

ctrl = Controller(world)

print()
print("######## INITIAL STATE ########")
ctrl.Inspect()

# ── 3. Drive the simulation ──────────────────────────────────────────────────

print()
print("######## STEP 1 - Alice queues two packets ########")
ctrl.Send("alice", b"Hello, Bob!",  Dst="bob", Seq=1)
ctrl.Send("alice", b"How are you?", Dst="bob", Seq=2)

print()
print("######## STEP 2 - Tick (packets flow alice -> wire -> bob in one tick) ########")
ctrl.Tick()

print()
print("######## STEP 3 - Drain Bob's RX ########")
ctrl.Drain("bob")

print()
print("######## STEP 4 - Bob replies, both directions same tick ########")
ctrl.Send("bob",   b"Hi Alice!", Dst="alice", Seq=1)
ctrl.Send("alice", b"ping!",     Dst="bob",   Seq=3)

print()
print("######## STEP 5 - Tick ########")
ctrl.Tick()

print()
print("######## STEP 6 - Both received in a single tick ########")
ctrl.Drain("alice")
ctrl.Drain("bob")
