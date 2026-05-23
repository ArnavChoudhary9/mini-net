# 04 — Switched LAN

> Source: [`examples/04_ethernet.py`](https://github.com/)

Three hosts behind a learning switch. Watch the MAC table fill in as
frames flow.

```bash
python examples/04_ethernet.py
```

## Topology

```text
      alice ─── wire_a ─── [port0]
                           [port1] ─── wire_b ─── bob
                           [port2] ─── wire_c ─── charlie
                           [port3] (unused)
                              switch
```

## Step 1 — Alice → Bob, switch knows nobody

```python
alice_eth.SendFrame(DstMac=bob_eth.Mac, Payload=b"Hello, Bob!", Seq=1)
ctrl.Tick(2)
```

What happens:

1. Tick 1: alice's frame lands on `wire_a`. Switch reads it on `port0`,
   learns `aa:... → port0`, doesn't know `bb:...`, **floods** to ports
   1, 2, 3.
2. Tick 2: floods reach Bob and Charlie. Port3 has no wire so its
   forwarded copy is silently dropped.

```text
ctrl.Drain("bob")     -> Frame(... Data=b'Hello, Bob!')
ctrl.Drain("charlie") -> Frame(... Data=b'Hello, Bob!')   # unwanted but normal
print(sw.MacTable)    -> {'aa:aa:aa:aa:aa:aa': 0}
```

## Step 2 — Bob → Alice, switch knows Alice

```python
bob_eth.SendFrame(DstMac=alice_eth.Mac, Payload=b"Hi Alice!", Seq=1)
ctrl.Tick(2)
```

Now the switch:

1. Learns `bb:... → port1` from the frame's source.
2. Looks up Alice's MAC in the table → hit on port0.
3. Forwards out port0 *only*. **No flood, Charlie gets nothing.**

```text
ctrl.Drain("alice")   -> Frame(... Data=b'Hi Alice!')
ctrl.Drain("charlie") -> RX empty
print(sw.MacTable)    -> {'aa:...': 0, 'bb:...': 1}
```

## Step 3 — Broadcast

```python
alice_eth.SendFrame(DstMac=MAC.BROADCAST, Payload=b"ANYBODY HOME?")
ctrl.Tick(2)
```

`MAC.IsBroadcast(frame.Dst)` is `True`, so the switch floods unconditionally
to every port except the source. Both Bob and Charlie receive.

## Step 4 — Alice → Bob again, fully learned

```python
alice_eth.SendFrame(DstMac=bob_eth.Mac, Payload=b"how about now?")
ctrl.Tick(2)
```

This time the table already has Bob. The switch forwards out port1
directly. Charlie's RX stays empty.

## Try it interactively

Two ways to drop into the REPL with this exact LAN:

```bash
python -m network ethernet           # built-in
python examples/05_ethernet_repl.py  # same topology, explicit code
```

Then drive frames by hand and watch the MAC table fill in:

```text
ctrl@lan> mactable sw
  sw MAC table is empty
ctrl@lan> frame alice bb:bb:bb:bb:bb:bb "hi" 1
ctrl@lan> tick 2
ctrl@lan> drain bob
ctrl@lan> mactable sw
  sw MAC table:
    aa:aa:aa:aa:aa:aa -> port0
ctrl@lan> frame bob aa:aa:aa:aa:aa:aa "yo" 1
ctrl@lan> tick 2
ctrl@lan> drain alice
ctrl@lan> mactable sw
  sw MAC table:
    aa:aa:aa:aa:aa:aa -> port0
    bb:bb:bb:bb:bb:bb -> port1
```

## Takeaways

- A switch with an empty table behaves like a hub (floods).
- A switch with a learned table behaves like a switch (forwards).
- Switching is a 2-tick operation per hop: one tick to land on the
  switch, one tick to land on the destination.
- Charlie receiving Step 1's frame is correct behaviour — flooding is
  exactly how the switch tells unknown destinations apart from known
  ones. The "leak" disappears once the table has every endpoint.
