"""Stock selection metrics: Jensen's Alpha, Sharpe Ratio, Information Ratio."""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import statsmodels.api as sm


@dataclass
class JensenAlphaResult:
    alpha: float              # annualized alpha
    beta: float
    alpha_p_value: float
    r_squared: float
    n_observations: int

    def is_significant(self, alpha_level: float = 0.05) -> bool:
        return self.alpha_p_value < alpha_level


@dataclass
class SharpeRatioResult:
    sharpe_ratio: float  # annualized
    annualized_return: float
    annualized_vol: float
    n_observations: int


@dataclass
class InformationRatioResult:
    information_ratio: float  # annualized
    tracking_error: float     # annualized
    active_return_mean: float
    n_observations: int


def _annualize_return(daily_mean: float) -> float:
    """Convert daily mean return to annualized (252 trading days)."""
    return (1 + daily_mean) ** 252 - 1


def _annualize_std(daily_std: float) -> float:
    """Convert daily std to annualized."""
    return daily_std * np.sqrt(252)


def _winsorize(arr: np.ndarray, limits: float = 0.01) -> np.ndarray:
    """Winsorize extreme values at given percentile limits."""
    lower = np.percentile(arr, limits * 100)
    upper = np.percentile(arr, (1 - limits) * 100)
    return np.clip(arr, lower, upper)


def calculate_jensen_alpha(
    fund_returns: np.ndarray,
    bench_returns: np.ndarray,
    rf_annual: float,
) -> Optional[JensenAlphaResult]:
    """CAPM regression: Rp - Rf = alpha + beta * (Rm - Rf) + epsilon.
    Returns JensenAlphaResult or None if regression fails."""
    n = len(fund_returns)
    if n < 20:
        return None

    # Convert annual risk-free rate to daily
    rf_daily = (1 + rf_annual) ** (1 / 252) - 1

    # Excess returns
    fund_excess = fund_returns - rf_daily
    bench_excess = bench_returns - rf_daily

    # Winsorize extreme values
    fund_excess = _winsorize(fund_excess)
    bench_excess = _winsorize(bench_excess)

    try:
        X = sm.add_constant(bench_excess)
        model = sm.OLS(fund_excess, X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})

        alpha_daily = model.params.iloc[0] if hasattr(model.params, 'iloc') else model.params[0]
        beta = model.params.iloc[1] if hasattr(model.params, 'iloc') else model.params[1]

        # p-value for alpha
        alpha_p = model.pvalues.iloc[0] if hasattr(model.pvalues, 'iloc') else model.pvalues[0]

        return JensenAlphaResult(
            alpha=_annualize_return(alpha_daily),
            beta=float(beta),
            alpha_p_value=float(alpha_p),
            r_squared=float(model.rsquared),
            n_observations=n,
        )
    except Exception:
        return None


def calculate_sharpe_ratio(
    fund_returns: np.ndarray,
    rf_annual: float,
) -> Optional[SharpeRatioResult]:
    """Sharpe Ratio = (mean(Rp) - Rf) / std(Rp), annualized."""
    n = len(fund_returns)
    if n < 5:
        return None

    rf_daily = (1 + rf_annual) ** (1 / 252) - 1
    excess = fund_returns - rf_daily

    mean_excess = np.mean(excess)
    std_excess = np.std(excess, ddof=1)

    if std_excess == 0:
        return None

    daily_sharpe = mean_excess / std_excess

    return SharpeRatioResult(
        sharpe_ratio=float(daily_sharpe * np.sqrt(252)),
        annualized_return=float(_annualize_return(np.mean(fund_returns))),
        annualized_vol=float(_annualize_std(np.std(fund_returns, ddof=1))),
        n_observations=n,
    )


def calculate_information_ratio(
    fund_returns: np.ndarray,
    bench_returns: np.ndarray,
) -> Optional[InformationRatioResult]:
    """Information Ratio = mean(Rp - Rb) / std(Rp - Rb), annualized."""
    n = len(fund_returns)
    if n < 5:
        return None

    active_returns = fund_returns - bench_returns
    mean_active = np.mean(active_returns)
    tracking_error = np.std(active_returns, ddof=1)

    if tracking_error == 0:
        return None

    daily_ir = mean_active / tracking_error

    return InformationRatioResult(
        information_ratio=float(daily_ir * np.sqrt(252)),
        tracking_error=float(_annualize_std(tracking_error)),
        active_return_mean=float(_annualize_return(mean_active)),
        n_observations=n,
    )


def calculate_cumulative_return(daily_returns) -> float:
    """Cumulative return as a decimal (e.g. 0.35 = +35%).

    Args:
        daily_returns: array of daily returns as decimals.
    """
    arr = np.asarray(daily_returns, dtype=float)
    if len(arr) == 0:
        return 0.0
    return float(np.prod(1.0 + arr) - 1.0)


def calculate_max_drawdown(daily_returns) -> float:
    """Maximum drawdown as a negative decimal (e.g. -0.23 = -23%).

    Computed from the running wealth curve: min(wealth / running_max - 1).

    Args:
        daily_returns: array of daily returns as decimals.
    """
    arr = np.asarray(daily_returns, dtype=float)
    if len(arr) == 0:
        return 0.0
    wealth = np.cumprod(1.0 + arr)
    running_max = np.maximum.accumulate(wealth)
    drawdown = wealth / running_max - 1.0
    return float(drawdown.min())
