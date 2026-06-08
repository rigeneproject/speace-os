"""Supervised services — directory marker per /etc/speace/services.

Ogni servizio è una directory con un eseguibile ``run``. Il supervisore
(``/lib/speace/supervisor.py``) lo lancia, ne controlla lo stato, lo
riavvia in caso di crash.
"""
