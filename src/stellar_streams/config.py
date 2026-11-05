from dataclasses import dataclass, asdict
from pathlib import Path
import math
import yaml


@dataclass(frozen=True)
class Config:
    seed: int = 42
    ruwe_max: float = 1.4
    parallax_snr_min: float = 5.0
    rv_error_max: float = 5.0
    halo_z_min_kpc: float = 3.0
    chunk_size: int = 50000
    max_stars: int = 100000
    sampling: str = "error"
    n_neighbors: int = 30
    n_components: int = 3
    min_dist: float = 0.0
    min_cluster_size: int = 120
    min_samples: int = 20
    cluster_selection_method: str = "leaf"
    position_weight: float = 1.0
    velocity_weight: float = 1.0
    stability_runs: int = 2
    plot_max_stars: int = 20000

    def __post_init__(self):
        ints = ("seed", "chunk_size", "max_stars", "n_neighbors", "n_components",
                "min_cluster_size", "min_samples", "stability_runs", "plot_max_stars")
        for key in ints:
            if type(getattr(self, key)) is not int:
                raise ValueError(f"{key} must be an integer")
        for key in ("chunk_size", "max_stars", "min_samples", "plot_max_stars"):
            if getattr(self, key) < 1:
                raise ValueError(f"{key} must be positive")
        if self.seed < 0 or self.stability_runs < 0:
            raise ValueError("seed and stability_runs must be nonnegative")
        if self.min_cluster_size < 2 or self.n_neighbors < 2:
            raise ValueError("min_cluster_size and n_neighbors must be >= 2")
        if self.max_stars <= max(self.min_cluster_size, self.n_neighbors):
            raise ValueError("max_stars must exceed min_cluster_size and n_neighbors")
        if self.n_components not in (2, 3):
            raise ValueError("n_components must be 2 or 3")
        if self.sampling not in ("error", "uniform"):
            raise ValueError("sampling must be error or uniform")
        if self.cluster_selection_method not in ("eom", "leaf"):
            raise ValueError("cluster_selection_method must be eom or leaf")
        for key in ("ruwe_max", "parallax_snr_min", "rv_error_max", "position_weight", "velocity_weight"):
            v = getattr(self, key)
            if not math.isfinite(v) or v <= 0:
                raise ValueError(f"{key} must be finite and positive")
        if not math.isfinite(self.min_dist) or not 0 <= self.min_dist <= 1:
            raise ValueError("min_dist must be between 0 and 1")
        if not math.isfinite(self.halo_z_min_kpc) or self.halo_z_min_kpc < 0:
            raise ValueError("halo_z_min_kpc must be finite and nonnegative")

    def to_dict(self):
        return asdict(self)


def load_config(path=None):
    if path is None:
        return Config()
    values = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(values, dict):
        raise ValueError("Config must be a YAML mapping")
    return Config(**values)
