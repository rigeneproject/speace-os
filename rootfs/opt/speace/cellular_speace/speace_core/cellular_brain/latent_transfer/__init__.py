"""Latent Transfer Layer — bio-inspired inter-module vector communication (T116)."""

from speace_core.cellular_brain.latent_transfer.latent_packet import LatentPacket, VectorSource
from speace_core.cellular_brain.latent_transfer.recursive_link_adapter import RecursiveLinkAdapter
from speace_core.cellular_brain.latent_transfer.vector_alignment import VectorAlignment
from speace_core.cellular_brain.latent_transfer.cross_node_latent_bus import CrossNodeLatentBus
from speace_core.cellular_brain.latent_transfer.latent_skill_transfer import LatentSkillTransfer

__all__ = [
    "LatentPacket",
    "VectorSource",
    "RecursiveLinkAdapter",
    "VectorAlignment",
    "CrossNodeLatentBus",
    "LatentSkillTransfer",
]
