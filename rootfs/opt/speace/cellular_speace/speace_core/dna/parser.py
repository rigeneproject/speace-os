import pathlib
from typing import Union

import yaml

from speace_core.dna.models import SharedGenome


def load_genome(path: Union[str, pathlib.Path]) -> SharedGenome:
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Genome file not found: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if data is None:
        data = {}
    return SharedGenome.model_validate(data)
