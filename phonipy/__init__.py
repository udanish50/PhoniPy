"""PhoniPy: voice note stability and harmonic purity, offline and reproducible."""

from .analysis import analyze_file, analyze_samples, frequency_to_key, key_to_frequency
from .audio import AudioError
from .batch import BatchResult, analyze_directory, parser
from .config import AnalysisConfig
from .metrics import compute_metrics
from .models import AnalysisResult, Frame, Metrics, Segment

__version__ = "0.1.0"
__all__ = [
    "AnalysisConfig",
    "AnalysisResult",
    "AudioError",
    "BatchResult",
    "Frame",
    "Metrics",
    "Segment",
    "analyze_directory",
    "analyze_file",
    "analyze_samples",
    "compute_metrics",
    "frequency_to_key",
    "key_to_frequency",
    "parser",
]
