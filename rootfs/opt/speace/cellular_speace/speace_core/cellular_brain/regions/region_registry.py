from typing import Dict, List, Optional

from speace_core.cellular_brain.regions.brain_region import BrainRegion, BrainRegionProfile
from speace_core.cellular_brain.regions.region_connectome import RegionConnectome


class RegionRegistry:
    """Holds all BrainRegion instances and their connectome."""

    def __init__(self):
        self.regions: Dict[str, BrainRegion] = {}
        self.connectome = RegionConnectome()

    def register(self, region: BrainRegion) -> None:
        self.regions[region.region_id] = region
        self.connectome.regions[region.region_id] = region.to_profile().model_dump()

    def get(self, region_id: str) -> Optional[BrainRegion]:
        return self.regions.get(region_id)

    def list_region_ids(self) -> List[str]:
        return list(self.regions.keys())

    def get_region_profiles(self) -> List[BrainRegionProfile]:
        return [r.to_profile() for r in self.regions.values()]

    def remove_region(self, region_id: str) -> None:
        self.regions.pop(region_id, None)
        self.connectome.regions.pop(region_id, None)
        self.connectome.remove_connections_involving(region_id)

    def compute_global_metrics(self) -> Dict[str, float]:
        if not self.regions:
            return {}
        profiles = [r.to_profile() for r in self.regions.values()]
        return {
            "mean_region_energy": sum(p.mean_energy for p in profiles) / len(profiles),
            "mean_region_phi": sum(p.local_phi for p in profiles) / len(profiles),
            "total_neurons_in_regions": sum(len(p.neuron_ids) for p in profiles),
            "connectome_density": self.connectome.compute_connectome_density(),
        }
