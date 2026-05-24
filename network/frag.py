"""
MTU and IP fragmentation.

Different physical links can carry packets of different maximum sizes
(MTU = Maximum Transmission Unit). When a router has to forward a
packet whose size exceeds the next link's MTU, it has two choices:

  - drop and send back ICMP "Fragmentation Needed" (this is what
    IPv6 mandates — path MTU discovery)
  - split the packet into smaller fragments that fit, and let the
    receiver reassemble (classic IPv4)

mini-net implements the classic IPv4 behaviour for educational value:

  - Wire grows an optional Mtu attribute (default unlimited).
  - Router compares Pkt size to the outgoing wire's MTU; if too big,
    it fragments using IPPacket's Identification / FragOffset /
    MoreFragments fields (added below).
  - EthernetIPInterface reassembles fragments by (Src, Dst, Identification)
    and delivers the original IPPacket to the application once complete.

Mini-net measures "size" as len(Data) — there are no protocol headers
to count. So MTU is "max payload bytes per fragment" rather than
"max packet bytes" in the strict sense.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .ip import IPPacket

logger = logging.getLogger(__name__)


# ── Extended IP packet with fragmentation fields ─────────────────────────────

@dataclass(frozen=True)
class FragmentedIPPacket(IPPacket):
    """
    An IPPacket that carries fragmentation metadata.

    Identification groups fragments of the same original packet.
    FragOffset is the byte offset of this fragment in the original payload.
    MoreFragments=True means another fragment follows.
    """
    Identification: int = 0
    FragOffset: int = 0
    MoreFragments: bool = False

    def __repr__(self) -> str:
        Mf = "+" if self.MoreFragments else ""
        return (f"IPFrag(Src={self.Src} Dst={self.Dst} TTL={self.TTL} "
                f"id={self.Identification} off={self.FragOffset}{Mf} "
                f"Data={self.Data!r})")


# ── Fragmentation helper ─────────────────────────────────────────────────────

_NextId = [0]


def _AllocateId() -> int:
    _NextId[0] = (_NextId[0] + 1) & 0xFFFF
    return _NextId[0]


def Fragment(Pkt: IPPacket, Mtu: int) -> list[FragmentedIPPacket]:
    """
    Split Pkt's Data into chunks of at most Mtu bytes each.

    Returns a list of FragmentedIPPacket sharing one Identification.
    The first fragment preserves any non-bytes payload only if it
    already fits in one fragment (we don't try to slice IcmpMessage
    payloads — the chunking is purely over bytes).
    """
    if not isinstance(Pkt.Data, (bytes, bytearray)):
        # Can't split a structured payload — return as-is wrapped as a
        # single fragment with MoreFragments=False.
        return [FragmentedIPPacket(
            Data=Pkt.Data, Src=Pkt.Src, Dst=Pkt.Dst, Seq=Pkt.Seq,
            TTL=Pkt.TTL, Protocol=Pkt.Protocol,
            Identification=_AllocateId(), FragOffset=0, MoreFragments=False,
        )]

    Data = bytes(Pkt.Data)
    if len(Data) <= Mtu:
        return [FragmentedIPPacket(
            Data=Data, Src=Pkt.Src, Dst=Pkt.Dst, Seq=Pkt.Seq,
            TTL=Pkt.TTL, Protocol=Pkt.Protocol,
            Identification=_AllocateId(), FragOffset=0, MoreFragments=False,
        )]

    Id = _AllocateId()
    Fragments: list[FragmentedIPPacket] = []
    Offset = 0
    while Offset < len(Data):
        Chunk = Data[Offset:Offset + Mtu]
        More = Offset + Mtu < len(Data)
        Fragments.append(FragmentedIPPacket(
            Data=Chunk, Src=Pkt.Src, Dst=Pkt.Dst, Seq=Pkt.Seq,
            TTL=Pkt.TTL, Protocol=Pkt.Protocol,
            Identification=Id, FragOffset=Offset, MoreFragments=More,
        ))
        Offset += Mtu
    return Fragments


# ── Reassembly state (used by EthernetIPInterface via Reassembler) ───────────

class Reassembler:
    """
    Per-host reassembly buffer.

    Keyed by (Src, Dst, Identification). Returns the original IPPacket
    once every fragment has arrived; returns None until then.
    """

    def __init__(self):
        self._Buckets: dict[tuple, list[FragmentedIPPacket]] = {}

    def Add(self, Frag: FragmentedIPPacket) -> Optional[IPPacket]:
        Key = (Frag.Src, Frag.Dst, Frag.Identification)
        Bucket = self._Buckets.setdefault(Key, [])
        Bucket.append(Frag)

        # Are we done? "Done" means we have a contiguous run from 0
        # up through some fragment with MoreFragments=False.
        Sorted = sorted(Bucket, key=lambda F: F.FragOffset)
        Expected = 0
        for F in Sorted:
            if F.FragOffset != Expected:
                return None
            Expected += len(F.Data)
            if not F.MoreFragments:
                # Complete — assemble payload and return as a regular IPPacket
                self._Buckets.pop(Key, None)
                Payload = b"".join(F2.Data for F2 in Sorted)
                logger.info("reassembled id=%d %d frags %d bytes",
                            Frag.Identification, len(Sorted), len(Payload))
                return IPPacket(
                    Data=Payload, Src=F.Src, Dst=F.Dst, Seq=F.Seq,
                    TTL=F.TTL, Protocol=F.Protocol,
                )
        return None
