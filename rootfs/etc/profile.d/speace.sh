#!/bin/sh
# Caricato da /etc/profile se esiste. Imposta l'ambiente SPEACE.
if [ -f /etc/speace/env.conf ]; then
    . /etc/speace/env.conf
fi
