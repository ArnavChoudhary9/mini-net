"""
ICMP — control / error messages for IP.

ICMP rides inside IP (Protocol=1). It's how the internet tells you
things like "TTL exceeded in transit", "destination unreachable", and
how ping works (echo request / echo reply).

This module adds:
  - IcmpType: the standard type constants
  - IcmpMessage: an IPPacket subclass with Type/Code/Identifier/SeqNumber
  - Builder helpers for the common message types

Routers send Time Exceeded when they drop a TTL=0 packet (see Router).
EthernetIPInterface auto-replies to Echo Requests (see arp.py).
"""

from dataclasses import dataclass

from .ip import IPPacket


# ── Type constants ───────────────────────────────────────────────────────────

class IcmpType:
    """Standard ICMP message types (subset that mini-net actually uses)."""
    ECHO_REPLY        = 0
    DEST_UNREACHABLE  = 3
    ECHO_REQUEST      = 8
    TIME_EXCEEDED     = 11

    NAMES = {
        0:  "echo-reply",
        3:  "dest-unreachable",
        8:  "echo-request",
        11: "time-exceeded",
    }


# ── ICMP message ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class IcmpMessage(IPPacket):
    """
    An ICMP message carried inside an IP packet (Protocol=1).

    Inherits Data, Src, Dst, Seq, TTL, Protocol from IPPacket and adds
    the four ICMP-specific fields. Type tells receivers what kind of
    message this is; Code refines it (e.g. Type=3 Code=1 = "host
    unreachable", Type=3 Code=3 = "port unreachable").

    Identifier / SeqNumber are used by echo (ping) to match replies
    back to the originating ping process.
    """
    Type: int = 0
    Code: int = 0
    Identifier: int = 0
    SeqNumber: int = 0

    def __repr__(self) -> str:
        Name = IcmpType.NAMES.get(self.Type, f"type-{self.Type}")
        Extra = ""
        if self.Type in (IcmpType.ECHO_REQUEST, IcmpType.ECHO_REPLY):
            Extra = f" id={self.Identifier} seq={self.SeqNumber}"
        return (f"ICMP({Name} Src={self.Src} Dst={self.Dst} "
                f"TTL={self.TTL}{Extra} Data={self.Data!r})")


# ── Builder helpers ──────────────────────────────────────────────────────────

def EchoRequest(Src: str, Dst: str, Identifier: int = 0,
                SeqNumber: int = 0, Data: bytes = b"", TTL: int = 64) -> IcmpMessage:
    return IcmpMessage(Data=Data, Src=Src, Dst=Dst, TTL=TTL, Protocol=1,
                       Type=IcmpType.ECHO_REQUEST,
                       Identifier=Identifier, SeqNumber=SeqNumber)


def EchoReply(Src: str, Dst: str, Identifier: int = 0,
              SeqNumber: int = 0, Data: bytes = b"", TTL: int = 64) -> IcmpMessage:
    return IcmpMessage(Data=Data, Src=Src, Dst=Dst, TTL=TTL, Protocol=1,
                       Type=IcmpType.ECHO_REPLY,
                       Identifier=Identifier, SeqNumber=SeqNumber)


def TimeExceeded(Src: str, Dst: str, TTL: int = 64) -> IcmpMessage:
    """Build a 'TTL expired in transit' ICMP message."""
    return IcmpMessage(Data=b"", Src=Src, Dst=Dst, TTL=TTL, Protocol=1,
                       Type=IcmpType.TIME_EXCEEDED, Code=0)


def DestUnreachable(Src: str, Dst: str, Code: int = 0,
                    TTL: int = 64) -> IcmpMessage:
    """Build a 'destination unreachable' ICMP message. Code 0 = network unreachable."""
    return IcmpMessage(Data=b"", Src=Src, Dst=Dst, TTL=TTL, Protocol=1,
                       Type=IcmpType.DEST_UNREACHABLE, Code=Code)
