"""Setup Python path for FHIR library imports."""

import sys
from pathlib import Path

# Add the parent fhir package to the Python path
fhir_src = Path(__file__).parent.parent.parent.parent / "fhir" / "src"
if fhir_src.exists():
    if str(fhir_src) not in sys.path:
        sys.path.insert(0, str(fhir_src))
else:
    # Try absolute path as fallback
    fhir_src_abs = Path("/Users/mike-nacey/Desktop/fhir/src")
    if fhir_src_abs.exists() and str(fhir_src_abs) not in sys.path:
        sys.path.insert(0, str(fhir_src_abs))
