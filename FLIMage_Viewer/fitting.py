"""
Decay curve fitting interface for FLIMage Viewer.
Wraps multi-exponential reconvolution fitting routines.
"""

import sys
import os
from typing import Dict, Any, Optional, Tuple
import numpy as np

# Add parent directory to path so Reconvolution_Fitting2 can be imported
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Python Script"))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from Reconvolution_Fitting2 import FLIMDecayFitter
except ImportError:
    FLIMDecayFitter = None


class DecayFitter:
    """Convenience decay curve fitter for desktop GUI and scripts."""

    def __init__(self, n_exp: int = 2, sync_rate_hz: Optional[float] = 80e6):
        self.n_exp = n_exp
        self.sync_rate_hz = sync_rate_hz
        self.last_result: Optional[Dict[str, Any]] = None

    def fit(
        self,
        time_ns: np.ndarray,
        counts: np.ndarray,
        fixed_params: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Fit decay curve using Gaussian-IRF convolved multi-exponential model.
        Returns:
            dict containing:
                'params': parameter dict (A1, tau1, [A2, tau2], t0, sigma, bg)
                'fitted_curve': ndarray of fitted curve
                'chi2': chi-square
                'red_chi2': reduced chi-square
                'residuals': data - fitted
        """
        if FLIMDecayFitter is None:
            raise RuntimeError("Reconvolution_Fitting2 is not available in Python Script path.")

        # Filter out NaN or negative values
        valid = (time_ns >= 0) & np.isfinite(counts)
        t = np.asarray(time_ns[valid], dtype=float)
        y = np.asarray(counts[valid], dtype=float)

        fitter = FLIMDecayFitter(
            n_exp=self.n_exp,
            sync_rate_hz=self.sync_rate_hz,
            time_unit="ns"
        )

        res = fitter.fit(t, y, fixed_params=fixed_params)

        fitted_curve = fitter.reconvolution_model(t, res.x_full)
        residuals = y - fitted_curve

        param_dict = {}
        for name, val in zip(fitter.param_names, res.x_full):
            param_dict[name] = float(val)

        # Compute fractional amplitudes for 2-exponential
        if self.n_exp == 2:
            a1 = param_dict.get("A1", 0.0)
            a2 = param_dict.get("A2", 0.0)
            tau1 = param_dict.get("tau1", 0.0)
            tau2 = param_dict.get("tau2", 0.0)
            total_amp = max(1e-12, a1 + a2)
            param_dict["f1_pop"] = a1 / total_amp
            param_dict["f2_pop"] = a2 / total_amp
            # Intensity-weighted lifetime
            total_int = max(1e-12, a1 * tau1 + a2 * tau2)
            param_dict["f1_int"] = (a1 * tau1) / total_int
            param_dict["f2_int"] = (a2 * tau2) / total_int
            param_dict["tau_mean_int"] = (a1 * tau1 * tau1 + a2 * tau2 * tau2) / total_int
            param_dict["tau_mean_amp"] = (a1 * tau1 + a2 * tau2) / total_amp

        self.last_result = {
            "params": param_dict,
            "fitted_curve": fitted_curve,
            "residuals": residuals,
            "chi2": float(res.chi2),
            "red_chi2": float(res.red_chi2),
            "time_ns": t,
            "counts": y,
        }
        return self.last_result
