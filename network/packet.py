from dataclasses import dataclass


@dataclass(frozen=True)
class Packet:
    Data: bytes
    Src: str = ""
    Dst: str = ""
    Seq: int = 0

    def __repr__(self) -> str:
        return f"Packet(Seq={self.Seq}, Src={self.Src!r}, Dst={self.Dst!r}, Data={self.Data!r})"
