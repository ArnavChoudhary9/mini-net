"""
01_foundation.py - Tick-Based Networking Basics
================================================

Building blocks, from the bottom up:

    Packet    - the unit of data
    Wire      - a one-directional FIFO buffer (the physical medium)
    Interface - a port on a node with a TX queue and a connected Wire
    Node      - a device that owns one or more interfaces

The simulation advances in discrete ticks. Each Node.Tick() flushes its
interfaces' TX queues onto their wires, modelling one step of transmission.

Duplex (automatically reading from the wire into an RX queue) is not yet
implemented — you will add that to Interface.Tick() yourself.
"""

import logging
from network import Node, Interface, Wire, Packet
from network.log import EnableLogging

EnableLogging(logging.INFO)   # change to logging.DEBUG to see wire-level detail

# ── 1. Packets ───────────────────────────────────────────────────────────────

print("=== PART 1 - Packet ===")

pkt = Packet(Data=b"Hello, network!", Src="alice", Dst="bob", Seq=1)
print(f"Created: {pkt}")
print()

# ── 2. Wire ──────────────────────────────────────────────────────────────────

print("=== PART 2 - Wire ===")

wire = Wire(Name="alice->bob")

wire.Put(Packet(Data=b"first",  Src="alice", Dst="bob", Seq=1))
wire.Put(Packet(Data=b"second", Src="alice", Dst="bob", Seq=2))

print(f"Wire empty? {wire.Empty}")
print(f"Got: {wire.Get()}")
print(f"Got: {wire.Get()}")
print(f"Wire empty? {wire.Empty}")
print()

# ── 3. Interface + Wire ───────────────────────────────────────────────────────

print("=== PART 3 - Interface ===")

wire_ab = Wire(Name="alice->bob")

alice_eth0 = Interface(Name="alice/eth0")
alice_eth0.Connect(wire_ab)

# Queue two packets for transmission
alice_eth0.Send(Packet(Data=b"ping 1", Src="alice", Dst="bob", Seq=1))
alice_eth0.Send(Packet(Data=b"ping 2", Src="alice", Dst="bob", Seq=2))

print("Before Tick: wire is empty?", wire_ab.Empty)

alice_eth0.Tick()   # flushes TX queue -> wire

print("After Tick:  wire is empty?", wire_ab.Empty)

# Manually drain the wire (duplex will automate this later)
print(f"wire.Get() -> {wire_ab.Get()}")
print(f"wire.Get() -> {wire_ab.Get()}")
print()

# ── 4. Nodes ──────────────────────────────────────────────────────────────────

print("=== PART 4 - Node ===")

alice = Node("alice")
bob   = Node("bob")

eth0_alice = alice.AddInterface("eth0")
eth0_bob   = bob.AddInterface("eth0")

# One wire from alice to bob (unidirectional for now)
wire_a_to_b = Wire(Name="alice->bob")
eth0_alice.Connect(wire_a_to_b)

# Alice sends, then ticks to flush onto the wire
alice.Send(Packet(Data=b"Hello, Bob!", Src="alice", Dst="bob", Seq=1))
alice.Send(Packet(Data=b"How are you?", Src="alice", Dst="bob", Seq=2))

alice.Tick()

# Bob's interface does not yet read from the wire automatically.
# TODO: connect eth0_bob to wire_a_to_b and implement Interface.Tick() duplex.
# For now, read the wire directly to confirm delivery:
print("Packets that reached the wire:")
while not wire_a_to_b.Empty:
    print(f"  {wire_a_to_b.Get()}")
print()

# ── 5. Disconnected interface ─────────────────────────────────────────────────

print("=== PART 5 - No wire attached ===")

lonely = Node("lonely")
eth0_lonely = lonely.AddInterface("eth0")

ok = lonely.Send(Packet(Data=b"Is anyone there?", Src="lonely", Dst="?"))
print(f"Send returned: {ok}  (False = no wire attached, packet discarded)")
