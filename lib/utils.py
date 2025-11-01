import datetime
import sys


def say(msg):
    """Log a message to stderr with timestamp."""
    d = datetime.datetime.now().replace(microsecond=0)
    sys.stderr.write(f'{d}: {str(msg)}\n')
    sys.stderr.flush()
