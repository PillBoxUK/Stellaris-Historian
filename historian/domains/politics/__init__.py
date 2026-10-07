"""Politics and diplomacy forensic diagnostics.

v0.0.46 deliberately keeps this domain diagnostic-only.  The probe inventories
retained player-country government/relations structures without promoting them
into public historical facts until the raw save shapes have been verified on
more than one campaign type.
"""

from .probe import write_politics_diplomacy_probe

__all__ = ["write_politics_diplomacy_probe"]
