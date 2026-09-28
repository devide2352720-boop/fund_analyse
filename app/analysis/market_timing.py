"""Market timing models: H-M (Henriksson-Merton) and T-M (Treynor-Mazuy)."""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import statsmodels.api as sm

from app.analysis.stock_selection import _winsorize


@dataclass
class HMResult:
    alpha: float          # annualized selectivity
    beta_1: float         # market beta
    beta_2: float         # timing coefficient (gamma)
    gamma_p_value: float
    r_squared: float
    n_observations: int

    def has_timing_ability(self, alpha_level: float = 0.05) -> bool:
        """Positive and significant gamma indicates market timing ability."""
        return self.beta_2 > 0 and self.gamma_p_value < alpha_level


@dataclass
class TMResult:
    alpha: float          # annualized selectivity
    beta_1: float         # market beta
    beta_2: float         # timing coefficient (gamma)
    gamma_p_value: float
    r_squared: float
    n_observations: int

    def has_timing_ability(self, alpha_level: float = 0.05) -> bool:
        return self.beta_2 > 0 and self.gamma_p_value < alpha_level


def _annualize_return(daily_mean: float) -> float:
    return (1 + daily_mean) ** 252 - 1


def calculate_hm_model(
    fund_returns: np.ndarray,
    bench_returns: np.ndarray,
    rf_annual: float,
) -> Optional[HMResult]:
    """Henriksson-Merton model:
    Rp - Rf = alpha + beta_1*(Rm - Rf) + beta_2*D*(Rm - Rf) + epsilon
    where D = 1 when (Rm - Rf) > 0, else 0.

    beta_2 > 0 and significant = fund increases beta in up markets (good timing).
    """
    n = len(fund_returns)
    if n < 20:
        return None

    rf_daily = (1 + rf_annual) ** (1 / 252) - 1

    fund_excess = _winsorize(fund_returns - rf_daily)
    bench_excess = _winsorize(bench_returns - rf_daily)

    # Dummy variable: 1 when market excess return > 0
    D = (bench_excess > 0).astype(float)
    interaction = D * bench_excess

    try:
        X = np.column_stack([np.ones(n), bench_excess, interaction])
        model = sm.OLS(fund_excess, X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})

        alpha_daily = model.params.iloc[0] if hasattr(model.params, 'iloc') else model.params[0]
        beta_1 = model.params.iloc[1] if hasattr(model.params, 'iloc') else model.params[1]
        beta_2 = model.params.iloc[2] if hasattr(model.params, 'iloc') else model.params[2]
        gamma_p = model.pvalues.iloc[2] if hasattr(model.pvalues, 'iloc') else model.pvalues[2]

        return HMResult(
            alpha=_annualize_return(alpha_daily),
            beta_1=float(beta_1),
            beta_2=float(beta_2),
            gamma_p_value=float(gamma_p),
            r_squared=float(model.rsquared),
            n_observations=n,
        )
    except Exception:
        return None


def calculate_tm_model(
    fund_returns: np.ndarray,
    bench_returns: np.ndarray,
    rf_annual: float,
) -> Optional[TMResult]:
    """Treynor-Mazuy model:
    Rp - Rf = alpha + beta_1*(Rm - Rf) + beta_2*(Rm - Rf)^2 + epsilon

    beta_2 > 0 and significant = convex relationship (good timing).
    """
    n = len(fund_returns)
    if n < 20:
        return None

    rf_daily = (1 + rf_annual) ** (1 / 252) - 1

    fund_excess = _winsorize(fund_returns - rf_daily)
    bench_excess = _winsorize(bench_returns - rf_daily)
    bench_excess_sq = bench_excess ** 2

    try:
        X = np.column_stack([np.ones(n), bench_excess, bench_excess_sq])
        model = sm.OLS(fund_excess, X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})

        alpha_daily = model.params.iloc[0] if hasattr(model.params, 'iloc') else model.params[0]
        beta_1 = model.params.iloc[1] if hasattr(model.params, 'iloc') else model.params[1]
        beta_2 = model.params.iloc[2] if hasattr(model.params, 'iloc') else model.params[2]
        gamma_p = model.pvalues.iloc[2] if hasattr(model.pvalues, 'iloc') else model.pvalues[2]

        return TMResult(
            alpha=_annualize_return(alpha_daily),
            beta_1=float(beta_1),
            beta_2=float(beta_2),
            gamma_p_value=float(gamma_p),
            r_squared=float(model.rsquared),
            n_observations=n,
        )
    except Exception:
        return None
