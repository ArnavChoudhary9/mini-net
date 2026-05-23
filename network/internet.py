import logging
from typing import Type, TypeVar

from .node import Node
from .wire import Wire

logger = logging.getLogger(__name__)

NodeT = TypeVar("NodeT", bound=Node)


class Internet:
    """
    The simulation world.

    Owns every Node and Wire in the network and is the single source of
    truth for advancing time. Internet.Tick() ticks every wire, then every
    node — so the whole world moves forward in one coherent step.
    """

    def __init__(self, Name: str = "internet"):
        self.Name = Name
        self._Nodes: list[Node] = []
        self._Wires: list[Wire] = []
        self._TickCount = 0
        logger.info("[%s] world created", self.Name)

    def AddNode(self, Name: str, Cls: Type[NodeT] = Node, **Kwargs) -> NodeT:
        """
        Create a node, register it, and return it.

        Pass `Cls=Switch` (or any other Node subclass) plus its keyword
        arguments to upgrade from a plain Node, e.g.

            world.AddNode("sw", Cls=Switch, Ports=4)
        """
        N = Cls(Name, **Kwargs)
        self._Nodes.append(N)
        logger.info("[%s] registered node '%s' (%s)",
                    self.Name, Name, Cls.__name__)
        return N

    def AddWire(self, Name: str, Capacity: int = 64,
                DropRate: float = 0.0) -> Wire:
        """Create a wire, register it, and return it."""
        W = Wire(Name=Name, Capacity=Capacity, DropRate=DropRate)
        self._Wires.append(W)
        logger.info("[%s] registered wire '%s' (drop_rate=%.2f)",
                    self.Name, Name, DropRate)
        return W

    def FindNode(self, Name: str) -> Node:
        for N in self._Nodes:
            if N.Name == Name:
                return N
        raise KeyError(f"Node '{Name}' not found in {self.Name}")

    def FindWire(self, Name: str) -> Wire:
        for W in self._Wires:
            if W.Name == Name:
                return W
        raise KeyError(f"Wire '{Name}' not found in {self.Name}")

    def Tick(self, Times: int = 1):
        """
        Advance the world by Times ticks using a two-phase tick:

          1. Tick every wire (propagation hook).
          2. FlushTx on every node — all outgoing packets land on wires.
          3. DrainRx on every node — all wires are read after everyone has
             finished transmitting.

        This ordering lets two nodes exchange packets within a single
        tick: by the time anyone reads the wire, all of this tick's
        transmissions are already there.
        """
        for _ in range(Times):
            self._TickCount += 1
            logger.info("[%s] ===== TICK %d =====", self.Name, self._TickCount)
            for W in self._Wires:
                W.Tick()
            for N in self._Nodes:
                N.FlushTx()
            for N in self._Nodes:
                N.DrainRx()

    @property
    def Nodes(self) -> list[Node]:
        return list(self._Nodes)

    @property
    def Wires(self) -> list[Wire]:
        return list(self._Wires)

    @property
    def TickCount(self) -> int:
        return self._TickCount
