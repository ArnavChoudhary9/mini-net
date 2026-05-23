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

    if not Log.handlers:
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
