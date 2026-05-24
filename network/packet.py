from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Packet:
    # Data is typed Any so the same field can hold a raw bytes payload
    # at L1/L2, an IPPacket as the payload of an EthernetFrame, or an
    # ArpMessage when the frame is ARP.  Mini-net doesn't actually
    # serialise to bytes — keeping the Python object is the whole point.
    Data: Any = b""
    Src: str = ""
    Dst: str = ""
    Seq: int = 0

    def __repr__(self) -> str:
        return f"Packet(Seq={self.Seq}, Src={self.Src!r}, Dst={self.Dst!r}, Data={self.Data!r})"
