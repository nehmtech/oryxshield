"""
OryxShield - Epidemiological Model Implementations
===========================================================

Production-ready ODE-based disease spread models solved with scipy.integrate.odeint.

Classes:
    SIRModel   – Susceptible-Infected-Recovered
    SEIRModel  – Susceptible-Exposed-Infected-Recovered
    SIRSModel  – SIR with waning immunity
    SEIRSModel – SEIR with waning immunity
    SISModel   – Susceptible-Infected-Susceptible

Factory:
    run_model(model_type, parameters, days) → results dict

All models compute R0, attack rate, peak day, and peak infections.
"""

import numpy as np
from scipy.integrate import odeint
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SIR
# =============================================================================

class SIRModel:
    """
    Susceptible – Infected – Recovered

    dS/dt = -β·S·I/N
    dI/dt =  β·S·I/N - γ·I
    dR/dt =  γ·I
    """

    def __init__(self, S0, I0, R0_init, beta, gamma):
        self.S0    = S0
        self.I0    = I0
        self.R0i   = R0_init   # initial recovered (not "R0")
        self.beta  = beta
        self.gamma = gamma
        self.N     = S0 + I0 + R0_init

    def _deriv(self, y, t):
        S, I, R = y
        dS = -self.beta * S * I / self.N
        dI =  self.beta * S * I / self.N - self.gamma * I
        dR =  self.gamma * I
        return dS, dI, dR

    def simulate(self, days):
        t        = np.linspace(0, days, days)
        solution = odeint(self._deriv, (self.S0, self.I0, self.R0i), t)
        S, I, R  = solution.T

        peak_idx       = int(np.argmax(I))
        attack_rate    = (self.S0 - S[-1]) / self.N * 100
        r0             = self.beta / self.gamma

        return {
            'days':           t.tolist(),
            'susceptible':    S.tolist(),
            'infected':       I.tolist(),
            'recovered':      R.tolist(),
            'peak_day':       peak_idx,
            'peak_infections': int(I[peak_idx]),
            'attack_rate':    float(attack_rate),
            'r0':             float(r0),
        }


# =============================================================================
# SEIR
# =============================================================================

class SEIRModel:
    """
    Susceptible – Exposed – Infected – Recovered

    dS/dt = -β·S·I/N
    dE/dt =  β·S·I/N - σ·E
    dI/dt =  σ·E      - γ·I
    dR/dt =  γ·I
    """

    def __init__(self, S0, E0, I0, R0_init, beta, sigma, gamma):
        self.S0    = S0
        self.E0    = E0
        self.I0    = I0
        self.R0i   = R0_init
        self.beta  = beta
        self.sigma = sigma
        self.gamma = gamma
        self.N     = S0 + E0 + I0 + R0_init

    def _deriv(self, y, t):
        S, E, I, R = y
        dS = -self.beta * S * I / self.N
        dE =  self.beta * S * I / self.N - self.sigma * E
        dI =  self.sigma * E - self.gamma * I
        dR =  self.gamma * I
        return dS, dE, dI, dR

    def simulate(self, days):
        t        = np.linspace(0, days, days)
        solution = odeint(self._deriv, (self.S0, self.E0, self.I0, self.R0i), t)
        S, E, I, R = solution.T

        peak_idx    = int(np.argmax(I))
        attack_rate = (self.S0 - S[-1]) / self.N * 100
        r0          = self.beta / self.gamma

        return {
            'days':           t.tolist(),
            'susceptible':    S.tolist(),
            'exposed':        E.tolist(),
            'infected':       I.tolist(),
            'recovered':      R.tolist(),
            'peak_day':       peak_idx,
            'peak_infections': int(I[peak_idx]),
            'attack_rate':    float(attack_rate),
            'r0':             float(r0),
        }


# =============================================================================
# SIRS
# =============================================================================

class SIRSModel:
    """
    SIR with waning immunity (ξ = rate of immunity loss R→S).

    dS/dt = -β·S·I/N + ξ·R
    dI/dt =  β·S·I/N  - γ·I
    dR/dt =  γ·I       - ξ·R
    """

    def __init__(self, S0, I0, R0_init, beta, gamma, xi):
        self.S0    = S0
        self.I0    = I0
        self.R0i   = R0_init
        self.beta  = beta
        self.gamma = gamma
        self.xi    = xi
        self.N     = S0 + I0 + R0_init

    def _deriv(self, y, t):
        S, I, R = y
        dS = -self.beta * S * I / self.N + self.xi * R
        dI =  self.beta * S * I / self.N - self.gamma * I
        dR =  self.gamma * I - self.xi * R
        return dS, dI, dR

    def simulate(self, days):
        t        = np.linspace(0, days, days)
        solution = odeint(self._deriv, (self.S0, self.I0, self.R0i), t)
        S, I, R  = solution.T

        peak_idx = int(np.argmax(I))
        r0       = self.beta / self.gamma

        return {
            'days':           t.tolist(),
            'susceptible':    S.tolist(),
            'infected':       I.tolist(),
            'recovered':      R.tolist(),
            'peak_day':       peak_idx,
            'peak_infections': int(I[peak_idx]),
            'attack_rate':    float((self.S0 - S[-1]) / self.N * 100),
            'r0':             float(r0),
        }


# =============================================================================
# SEIRS
# =============================================================================

class SEIRSModel:
    """
    SEIR with waning immunity.

    dS/dt = -β·S·I/N + ξ·R
    dE/dt =  β·S·I/N  - σ·E
    dI/dt =  σ·E       - γ·I
    dR/dt =  γ·I       - ξ·R
    """

    def __init__(self, S0, E0, I0, R0_init, beta, sigma, gamma, xi):
        self.S0    = S0
        self.E0    = E0
        self.I0    = I0
        self.R0i   = R0_init
        self.beta  = beta
        self.sigma = sigma
        self.gamma = gamma
        self.xi    = xi
        self.N     = S0 + E0 + I0 + R0_init

    def _deriv(self, y, t):
        S, E, I, R = y
        dS = -self.beta * S * I / self.N + self.xi * R
        dE =  self.beta * S * I / self.N  - self.sigma * E
        dI =  self.sigma * E - self.gamma * I
        dR =  self.gamma * I - self.xi * R
        return dS, dE, dI, dR

    def simulate(self, days):
        t        = np.linspace(0, days, days)
        solution = odeint(self._deriv, (self.S0, self.E0, self.I0, self.R0i), t)
        S, E, I, R = solution.T

        peak_idx = int(np.argmax(I))
        r0       = self.beta / self.gamma

        return {
            'days':           t.tolist(),
            'susceptible':    S.tolist(),
            'exposed':        E.tolist(),
            'infected':       I.tolist(),
            'recovered':      R.tolist(),
            'peak_day':       peak_idx,
            'peak_infections': int(I[peak_idx]),
            'attack_rate':    float((self.S0 - S[-1]) / self.N * 100),
            'r0':             float(r0),
        }


# =============================================================================
# SIS
# =============================================================================

class SISModel:
    """
    Susceptible – Infected – Susceptible (no lasting immunity).

    dS/dt = -β·S·I/N + γ·I
    dI/dt =  β·S·I/N  - γ·I
    """

    def __init__(self, S0, I0, beta, gamma):
        self.S0    = S0
        self.I0    = I0
        self.beta  = beta
        self.gamma = gamma
        self.N     = S0 + I0

    def _deriv(self, y, t):
        S, I = y
        dS = -self.beta * S * I / self.N + self.gamma * I
        dI =  self.beta * S * I / self.N - self.gamma * I
        return dS, dI

    def simulate(self, days):
        t        = np.linspace(0, days, days)
        solution = odeint(self._deriv, (self.S0, self.I0), t)
        S, I     = solution.T

        peak_idx = int(np.argmax(I))
        r0       = self.beta / self.gamma

        return {
            'days':           t.tolist(),
            'susceptible':    S.tolist(),
            'infected':       I.tolist(),
            'peak_day':       peak_idx,
            'peak_infections': int(I[peak_idx]),
            'attack_rate':    float((self.N - S[-1]) / self.N * 100),
            'r0':             float(r0),
        }


# =============================================================================
# FACTORY
# =============================================================================

def run_model(model_type, parameters, days=365):
    """
    Instantiate and run the appropriate epidemiological model.

    Args:
        model_type (str):  One of SIR, SEIR, SIRS, SEIRS, SIS, CUSTOM.
        parameters (dict): Must contain initial conditions AND rate parameters.
                           Missing rate parameters receive epidemiologically
                           sensible defaults so simulation never crashes on
                           incomplete model records.
        days (int):        Simulation horizon.

    Returns:
        dict: Simulation results including compartment time-series and metrics.

    Raises:
        ValueError: For unsupported model types.
    """
    def _f(key, default=0.0):
        """Return float(parameters[key]) or default when value is absent/None."""
        v = parameters.get(key)
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    # Initial compartment sizes — must be positive
    S0  = max(1, _f('initial_susceptible', 990))
    I0  = max(1, _f('initial_infected',     10))
    R0i = max(0, _f('initial_recovered',     0))
    E0  = max(0, _f('initial_exposed',       0))

    # Rate parameters with epidemiologically sensible defaults
    gamma = _f('gamma') or 0.1        # recovery rate  (~10 days)
    sigma = _f('sigma') or 0.196      # incubation rate (~5.1 days, COVID-like)
    xi    = _f('xi')    or 0.02       # waning rate     (~50 days immunity)

    # beta: prefer stored value; otherwise derive from stored R0 * gamma
    beta_raw = parameters.get('beta')
    if beta_raw is not None:
        beta = float(beta_raw)
    else:
        r0_stored = (parameters.get('r0')
                     or parameters.get('basic_reproduction_number'))
        if r0_stored is not None:
            beta = float(r0_stored) * gamma
        else:
            beta = 0.25  # implies R0 ≈ 2.5 with default gamma=0.1

    logger.info(
        "Running %s model: S0=%g I0=%g days=%d beta=%.4f gamma=%.4f",
        model_type, S0, I0, days, beta, gamma,
    )

    try:
        if model_type == 'SIR':
            return SIRModel(S0, I0, R0i, beta, gamma).simulate(days)

        if model_type == 'SEIR':
            return SEIRModel(S0, E0, I0, R0i, beta, sigma, gamma).simulate(days)

        if model_type == 'SIRS':
            return SIRSModel(S0, I0, R0i, beta, gamma, xi).simulate(days)

        if model_type == 'SEIRS':
            return SEIRSModel(S0, E0, I0, R0i, beta, sigma, gamma, xi).simulate(days)

        if model_type == 'SIS':
            return SISModel(S0, I0, beta, gamma).simulate(days)

        if model_type == 'CUSTOM':
            # Fall back to SIR with whatever parameters are provided
            logger.info("CUSTOM model – falling back to SIR dynamics")
            return SIRModel(S0, I0, R0i, beta, gamma).simulate(days)

        raise ValueError(f"Unsupported model type: {model_type}")

    except Exception as exc:
        logger.error("run_model error (type=%s): %s", model_type, exc, exc_info=True)
        raise