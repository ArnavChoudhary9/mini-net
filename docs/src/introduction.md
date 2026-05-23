# Introduction

**mini-net** is a tiny, hackable network simulator. It exists to help you learn
how the internet actually works by building it, piece by piece, in Python.

There is **no magic** in this library. Every line is something you could have
written. The whole codebase is small enough to read in one sitting.

## What you'll build

```text
        +-------+                          +-------+
        | alice |-- eth0 -- wire -- eth0 --|  bob  |
        +-------+                          +-------+
```

A world of `Node`s connected by `Wire`s. Data flows through `Packet`s. Time
advances in discrete `Tick`s. You drive the whole thing from a `Controller`
that doubles as an interactive REPL.

## What you'll learn

- How a physical link is just a FIFO buffer
- How an interface separates the "queue something to send" act from the
  "actually transmit it" act
- Why simultaneous bidirectional communication is harder than it sounds
- What a simulation clock is and why it has to be globally coordinated
- How packets traverse multiple hops (after you wire it up yourself)

## What the library does *not* do

It is intentionally incomplete. Specifically:

- `Interface.Tick()` only **transmits**. The **receive** side is your job
  (see the [duplex challenge](./duplex-challenge.md)).
- There is no routing. After duplex works, you'll add it.
- There is no protocol stack (no TCP, no IP, no Ethernet headers). Packets
  carry whatever fields you put in them.

This is the whole point. Each missing piece is a learning exercise.

## How to read these docs

1. Read [Getting Started](./getting-started.md) to install and run the examples.
2. Skim the **Components** chapters in order — they build on each other.
3. Walk through the three **Walkthrough** examples, ideally with the code open
   beside you.
4. Tackle the [Duplex Challenge](./duplex-challenge.md).

If you'd rather just read code, the whole library is six small files
under [`network/`](https://github.com/) — start with `packet.py` and
work outward.
