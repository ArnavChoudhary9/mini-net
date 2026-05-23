import logging
import shlex

from .packet import Packet
from .internet import Internet
from .ethernet import EthernetInterface, Switch, MAC

logger = logging.getLogger(__name__)


class Controller:
    """
    A debugger / inspector for an Internet.

    Wraps a world and exposes high-level commands you can drive from
    code or a REPL:

        ctrl.Send("alice", b"hi", Dst="bob")  # queue a packet
        ctrl.Tick()                            # advance one tick
        ctrl.Inspect()                         # print wire + queue state
        ctrl.Drain("bob")                      # read everything in RX

    Every command prints what it did so you can watch the simulation
    flow on the console.
    """

    def __init__(self, Internet_: Internet, Name: str = "ctrl"):
        self.Name = Name
        self._Internet = Internet_
        logger.info("[%s] attached to '%s'", self.Name, Internet_.Name)

    # ── actions ──────────────────────────────────────────────────────────────

    def Send(self, NodeName: str, Data: bytes, Dst: str = "",
             Seq: int = 0, IfaceIndex: int = 0) -> bool:
        """Build a Packet and queue it on the named node's interface."""
        N = self._Internet.FindNode(NodeName)
        Pkt = Packet(Data=Data, Src=NodeName, Dst=Dst, Seq=Seq)
        print(f"[{self.Name}] -> {NodeName} eth{IfaceIndex}.Send  {Pkt}")
        return N.Send(Pkt, IfaceIndex)

    def Tick(self, Times: int = 1, ShowState: bool = True):
        """Advance the world by Times ticks, then print the resulting state."""
        print(f"[{self.Name}] tick x{Times}")
        self._Internet.Tick(Times)
        if ShowState:
            self.Inspect()

    def Drain(self, NodeName: str, IfaceIndex: int = 0) -> int:
        """Read every packet in a node's RX queue and print each one."""
        N = self._Internet.FindNode(NodeName)
        Count = 0
        while True:
            Pkt = N.Receive(IfaceIndex)
            if Pkt is None:
                break
            print(f"[{self.Name}] <- {NodeName} eth{IfaceIndex} got    {Pkt}")
            Count += 1
        if Count == 0:
            print(f"[{self.Name}] <- {NodeName} eth{IfaceIndex} RX empty")
        return Count

    # ── inspection ───────────────────────────────────────────────────────────

    def Inspect(self):
        """Print a complete snapshot of the world."""
        print(f"[{self.Name}] ----- state @ tick {self._Internet.TickCount} -----")
        self._PrintWires()
        self._PrintNodes()
        print(f"[{self.Name}] ---------------------------")

    def PeekWire(self, WireName: str) -> list[Packet]:
        """Return (and print) every packet currently in transit on a wire."""
        W = self._Internet.FindWire(WireName)
        Buf = W.Peek()
        if Buf:
            print(f"[{self.Name}] wire {WireName!r} carries {len(Buf)}:")
            for P in Buf:
                print(f"      - {P}")
        else:
            print(f"[{self.Name}] wire {WireName!r} is empty")
        return Buf

    # ── helpers ──────────────────────────────────────────────────────────────

    def _PrintWires(self):
        for W in self._Internet.Wires:
            Buf = W.Peek()
            Tag = f"{W.Size} in flight" if Buf else "empty"
            Drop = f" dropped={W.Dropped}" if W.Dropped else ""
            print(f"      wire  {W.Name:<20} [{Tag}]{Drop}")
            for P in Buf:
                print(f"            - {P}")

    def _PrintNodes(self):
        for N in self._Internet.Nodes:
            Tag = f" ({type(N).__name__})" if type(N).__name__ != "Node" else ""
            print(f"      node  {N.Name}{Tag}")
            for Iface in N.Interfaces:
                MacStr = f" MAC={Iface.Mac}" if isinstance(Iface, EthernetInterface) else ""
                print(f"            iface {Iface.Name:<20} "
                      f"TX={Iface.TxSize} RX={Iface.RxSize} "
                      f"wire={Iface.WireName!r}{MacStr}")
            if isinstance(N, Switch):
                if N.MacTable:
                    Entries = ", ".join(f"{M}->port{P}" for M, P in N.MacTable.items())
                    print(f"            MAC table: {Entries}")
                else:
                    print(f"            MAC table: (empty)")

    @property
    def Internet(self) -> Internet:
        return self._Internet

    # ── interactive REPL ─────────────────────────────────────────────────────

    def Repl(self):
        """
        Launch an interactive console.

        Type 'help' for the command list. Ctrl-D or 'quit' to leave.
        """
        Banner = (
            f"\nmini-net controller '{self.Name}' attached to "
            f"'{self._Internet.Name}'\n"
            f"type 'help' for commands, 'quit' to exit\n"
        )
        print(Banner)

        Dispatch = {
            "help":     self._CmdHelp,
            "?":        self._CmdHelp,
            "tick":     self._CmdTick,
            "t":        self._CmdTick,
            "send":     self._CmdSend,
            "s":        self._CmdSend,
            "frame":    self._CmdFrame,
            "f":        self._CmdFrame,
            "drain":    self._CmdDrain,
            "d":        self._CmdDrain,
            "peek":     self._CmdPeek,
            "p":        self._CmdPeek,
            "inspect":  self._CmdInspect,
            "i":        self._CmdInspect,
            "nodes":    self._CmdNodes,
            "wires":    self._CmdWires,
            "mactable": self._CmdMacTable,
            "m":        self._CmdMacTable,
            "log":      self._CmdLog,
        }

        Prompt = f"{self.Name}@{self._Internet.Name}> "

        while True:
            try:
                Line = input(Prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not Line:
                continue

            try:
                Parts = shlex.split(Line)
            except ValueError as E:
                print(f"  parse error: {E}")
                continue

            Cmd, Args = Parts[0].lower(), Parts[1:]

            if Cmd in ("quit", "exit", "q"):
                break

            Handler = Dispatch.get(Cmd)
            if Handler is None:
                print(f"  unknown command: {Cmd!r}  (try 'help')")
                continue

            try:
                Handler(Args)
            except Exception as E:
                print(f"  error: {E}")

        print(f"[{self.Name}] bye")

    # ── command implementations ──────────────────────────────────────────────

    def _CmdHelp(self, _Args):
        print("""
  commands:
    send <node> <data> [dst] [seq]         queue a raw packet on a node    (alias: s)
    frame <node> <dst_mac> <data> [seq]    queue an Ethernet frame         (alias: f)
    tick [n]                               advance the world by n ticks    (alias: t)
    drain <node> [iface]                   read & print everything in RX   (alias: d)
    peek <wire>                            show packets in flight on wire  (alias: p)
    inspect                                full snapshot of the world      (alias: i)
    mactable <switch>                      show a switch's learned table   (alias: m)
    nodes                                  list all nodes & interfaces
    wires                                  list all wires
    log <level>                            set log level: debug/info/warning/off
    help                                   this message                    (alias: ?)
    quit                                   exit                            (alias: q, exit, ^D)
""")

    def _CmdTick(self, Args):
        Times = int(Args[0]) if Args else 1
        self.Tick(Times)

    def _CmdSend(self, Args):
        if len(Args) < 2:
            print("  usage: send <node> <data> [dst] [seq]")
            return
        NodeName = Args[0]
        Data = Args[1].encode()
        Dst = Args[2] if len(Args) > 2 else ""
        Seq = int(Args[3]) if len(Args) > 3 else 0
        self.Send(NodeName, Data, Dst=Dst, Seq=Seq)

    def _CmdFrame(self, Args):
        if len(Args) < 3:
            print("  usage: frame <node> <dst_mac> <data> [seq]")
            return
        NodeName, DstMac, Data = Args[0], Args[1], Args[2].encode()
        Seq = int(Args[3]) if len(Args) > 3 else 0
        N = self._Internet.FindNode(NodeName)
        if not N.Interfaces:
            print(f"  {NodeName} has no interfaces")
            return
        Iface = N.Interfaces[0]
        if not isinstance(Iface, EthernetInterface):
            print(f"  {Iface.Name} is not an EthernetInterface")
            return
        if DstMac.lower() == "broadcast":
            DstMac = MAC.BROADCAST
        if not MAC.IsValid(DstMac):
            print(f"  invalid dst MAC: {DstMac!r}")
            return
        Iface.SendFrame(DstMac=DstMac, Payload=Data, Seq=Seq)
        print(f"[{self.Name}] -> {NodeName} eth0.SendFrame  "
              f"Src={Iface.Mac} Dst={DstMac} Data={Data!r}")

    def _CmdMacTable(self, Args):
        if not Args:
            print("  usage: mactable <switch>")
            return
        N = self._Internet.FindNode(Args[0])
        if not isinstance(N, Switch):
            print(f"  {Args[0]} is not a Switch")
            return
        if not N.MacTable:
            print(f"  {N.Name} MAC table is empty")
            return
        print(f"  {N.Name} MAC table:")
        for M, P in N.MacTable.items():
            print(f"    {M} -> port{P}")

    def _CmdDrain(self, Args):
        if not Args:
            print("  usage: drain <node> [iface]")
            return
        IfaceIndex = int(Args[1]) if len(Args) > 1 else 0
        self.Drain(Args[0], IfaceIndex)

    def _CmdPeek(self, Args):
        if not Args:
            print("  usage: peek <wire>")
            return
        self.PeekWire(Args[0])

    def _CmdInspect(self, _Args):
        self.Inspect()

    def _CmdNodes(self, _Args):
        for N in self._Internet.Nodes:
            print(f"  {N.Name}")
            for I, Iface in enumerate(N.Interfaces):
                print(f"    [{I}] {Iface.Name}  TX={Iface.TxSize} "
                      f"RX={Iface.RxSize}  wire={Iface.WireName!r}")

    def _CmdWires(self, _Args):
        for W in self._Internet.Wires:
            print(f"  {W.Name:<20} size={W.Size}  dropped={W.Dropped}")

    def _CmdLog(self, Args):
        if not Args:
            print("  usage: log <debug|info|warning|off>")
            return
        Level = Args[0].lower()
        Log = logging.getLogger("network")
        if Level == "off":
            Log.setLevel(logging.CRITICAL + 1)
            print("  logging: off")
            return
        Map = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING}
        if Level not in Map:
            print(f"  unknown level: {Level!r}")
            return
        if not Log.handlers or all(isinstance(H, logging.NullHandler) for H in Log.handlers):
            H = logging.StreamHandler()
            H.setFormatter(logging.Formatter("%(levelname)-8s %(name)s: %(message)s"))
            Log.addHandler(H)
            Log.propagate = False
        Log.setLevel(Map[Level])
        print(f"  logging: {Level}")
