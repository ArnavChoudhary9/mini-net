import logging
import random
from collections import deque
from typing import Optional

from .packet import Packet

logger = logging.getLogger(__name__)


# A frame is what actually travels on the wire: a packet plus the
# name of the interface that put it there. Interfaces use the sender
# tag to avoid picking up their own transmissions.
Frame = tuple[Packet, str]


class Wire:
    """
    A FIFO buffer that carries (Packet, sender) frames between interfaces.

    Sender is a free-form string — typically an interface name like
    'alice/eth0'. The wire itself does not interpret it; it is just a
    tag the receiving interface can compare against its own name.

    DropRate (0.0 - 1.0) makes Put() randomly drop incoming packets,
    simulating a lossy link. Drops bump the Dropped counter and emit
    a warning log.
    """

    def __init__(self, Name: str = "wire", Capacity: int = 64, DropRate: float = 0.0):
        if not (0.0 <= DropRate <= 1.0):
            raise ValueError(f"DropRate must be in [0.0, 1.0], got {DropRate}")
        self.Name = Name
        self._Buffer: deque[Frame] = deque()
        self._Capacity = Capacity
        self._DropRate = DropRate
        self._Dropped = 0

    def Put(self, Packet_: Packet, Sender: str = "") -> bool:
        """
        Place a packet on the wire tagged with its sender. Returns False
        when dropped — either because the buffer is full or because of
        random link loss (DropRate).
        """
        if len(self._Buffer) >= self._Capacity:
            self._Dropped += 1
            logger.warning("[%s] buffer full — dropped %s", self.Name, Packet_)
            return False
        if self._DropRate > 0.0 and random.random() < self._DropRate:
            self._Dropped += 1
            logger.warning("[%s] random drop (p=%.2f) — lost %s",
                           self.Name, self._DropRate, Packet_)
            return False
        self._Buffer.append((Packet_, Sender))
        return True

    def Get(self) -> Optional[Packet]:
        """Pop the next packet (drops the sender tag). None if empty."""
        if not self._Buffer:
            return None
        Packet_, _Sender = self._Buffer.popleft()
        return Packet_

    def Frames(self) -> list[Frame]:
        """Non-consuming snapshot of every (packet, sender) frame on the wire."""
        return list(self._Buffer)

    def Consume(self, Frame_: Frame):
        """Remove a specific frame (typically called by the receiving interface)."""
        try:
            self._Buffer.remove(Frame_)
        except ValueError:
            pass

    def Tick(self):
        """Advance one simulation step. Hook for future propagation-delay modelling."""
        pass

    def Peek(self) -> list[Packet]:
        """Non-consuming list of just the packets on the wire (no sender tags)."""
        return [P for P, _ in self._Buffer]

    @property
    def Size(self) -> int:
        return len(self._Buffer)

    @property
    def Empty(self) -> bool:
        return len(self._Buffer) == 0

    @property
    def Dropped(self) -> int:
        return self._Dropped

    @property
    def DropRate(self) -> float:
        return self._DropRate
