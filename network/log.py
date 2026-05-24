"""
Logging helpers for mini-net.

By default the 'mini_net' logger uses a NullHandler (library best practice).
Call EnableLogging() at the top of your script to see simulation events.
"""

import logging

_ROOT = "network"


def EnableLogging(Level: int = logging.DEBUG):
    """
    Configure the mini-net logger to print to stdout.

    Call once at the start of your script:
        from network.log import EnableLogging
        EnableLogging()            # DEBUG and above
        EnableLogging(logging.INFO)  # INFO and above only
    """
    Log = logging.getLogger(_ROOT)
    Log.setLevel(Level)

    # The package __init__ installs a NullHandler so the library is silent
    # by default — that handler shows up in Log.handlers. We need to add a
    # real StreamHandler if there isn't one already, regardless of any
    # NullHandlers that might exist.
    HasStream = any(
        isinstance(H, logging.StreamHandler) and not isinstance(H, logging.NullHandler)
        for H in Log.handlers
    )
    if not HasStream:
        Handler = logging.StreamHandler()
        Handler.setFormatter(
            logging.Formatter("%(levelname)-8s %(name)s: %(message)s")
        )
        Log.addHandler(Handler)

    Log.propagate = False


def DisableLogging():
    """Silence all mini-net log output."""
    logging.getLogger(_ROOT).addHandler(logging.NullHandler())
    logging.getLogger(_ROOT).propagate = False
