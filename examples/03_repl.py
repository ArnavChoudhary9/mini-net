"""
03_repl.py - Interactive Controller Console
============================================

Builds the 2-node network and drops you into an interactive REPL.
Type 'help' once inside to see all commands.

Example session:

    ctrl@world> nodes
    ctrl@world> send alice "Hello, Bob!" bob
    ctrl@world> tick
    ctrl@world> peek link
    ctrl@world> drain bob
    ctrl@world> log debug
    ctrl@world> tick
    ctrl@world> quit
"""

from network import Internet, Controller

# ── Build the world ──────────────────────────────────────────────────────────

world = Internet("world")

alice = world.AddNode("alice")
bob   = world.AddNode("bob")

link  = world.AddWire("link", Capacity=8)

alice.AddInterface("eth0").Connect(link)
bob.AddInterface("eth0").Connect(link)

# ── Hand control to the user ─────────────────────────────────────────────────

ctrl = Controller(world)
ctrl.Repl()
