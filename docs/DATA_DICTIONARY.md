# Input data and catalog definitions

## Required observables

| Column | Unit / format | Treatment |
| --- | --- | --- |
| `source_id` | Decimal string or exact integer | Gaia DR3 identity; no floating-point conversion |
| `ra` | degrees, 0 <= RA < 360 | ICRS right ascension |
| `dec` | degrees, -90 <= Dec <= 90 | ICRS declination |
| `parallax` | milliarcseconds | Positive; inverse gives distance in kpc |
| `parallax_error` | milliarcseconds | Positive uncertainty |
| `parallax_over_error` | dimensionless | Must exceed 5; actual parallax/error ratio is also checked |
| `pmra` | mas/year | Gaia convention includes cos(dec); passed as Astropy `pm_ra_cosdec` |
| `pmdec` | mas/year | Declination proper motion |
| `radial_velocity` | km/s | Line-of-sight velocity |
| `radial_velocity_error` | km/s | Positive, below 5 |
| `ruwe` | dimensionless | Positive, below 1.4 |

`phot_g_mean_mag` (mag) and `random_index` are queried and retained when present,
but neither is a clustering feature. All required numeric inputs must be finite.
Thresholds are configurable and inequalities are strict. VOTables use the same
column names. Large VOTables should be converted to CSV before processing.

## Frame and features

| Setting | Adopted value |
| --- | --- |
| Sun-Galactic-center distance | 8.122 kpc |
| Solar height | 20.8 pc |
| Solar velocity in the adopted Cartesian frame | (12.9, 245.6, 7.78) km/s |
| Galactic center ICRS direction | (266.4051, -28.936175) degrees |
| Frame roll | 0 degrees |

These values are set explicitly in `preprocessing.py`, following the Astropy
v4.0 parameter convention. Astropy's Cartesian axes and sign conventions are
used. With the adopted convention the Sun is approximately on negative x.
The halo criterion is `abs(z_kpc) > 3.0`.

Only `x_kpc`, `y_kpc`, `z_kpc`, `vx_kms`, `vy_kms`, `vz_kms` enter the learner.
Each feature is centered on its sample median and divided by its interquartile
range with scikit-learn RobustScaler's handling of constant features. Weights
are applied after scaling. UMAP axes are dimensionless, without physical scale.

## Candidate diagnostics

| Column | Definition |
| --- | --- |
| `cluster_id` | HDBSCAN label; -1 means noise in star assignments |
| `n_members` | All assigned members, with no strength threshold applied |
| `membership_strength` | HDBSCAN density-based assignment strength, 0 to 1 |
| `outlier_score` | HDBSCAN GLOSH outlier score; larger values suggest stronger outliers |
| `cluster_persistence` | Relative persistence within the HDBSCAN density hierarchy |
| `seed_jaccard_mean` | Mean best membership Jaccard across additional UMAP seeds; blank when no extra runs are requested |
| `direct_6d_best_jaccard` | Best membership Jaccard with a cluster from direct scaled-6D HDBSCAN |
| `original_6d_supported` | Descriptive flag for direct-6D Jaccard >= 0.5; this does not confirm a physical stream |
| `position_elongation` | Square root of largest/smallest positional covariance eigenvalue; a morphology indicator |
| `velocity_dispersion_3d_kms` | Square root of the summed sample variances of vx, vy, vz; includes streaming gradients |
| `median_*` | Median physical coordinate/velocity of the assigned members |
| `status` | `unvalidated_density_candidate`; a computational group without physical confirmation |

Jaccard(A,B) = |A intersection B| / |A union B|. Each baseline candidate finds its
best overlap independently in the extra-seed or direct-6D control partition;
this is not a one-to-one global cluster assignment.
Seed checks do not perturb measurement uncertainties. ARI diagnostics including
noise treat noise as a single label and should be read alongside cluster-level
scores and false assignment rates.

## Historical outputs

Algorithm-comparison and published-reference-validation workflows were removed
on 2026-10-29. Older saved folders may contain their tables and metadata. The
current pipeline does not generate those outputs and the explorer does not load
them. Synthetic truth remains separate from the six clustering features and is
used only to evaluate generated toy demonstrations.
