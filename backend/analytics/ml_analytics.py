"""
OryxShield - Machine Learning Analytics
================================================

Two production-ready ML analytics functions.

Functions:
    arima_forecast    – ARIMA time-series forecasting with confidence intervals
    detect_anomalies  – Z-score based anomaly detection
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)


def arima_forecast(time_series, forecast_days=30):
    """
    ARIMA(1,1,1) time-series forecasting.

    Args:
        time_series (list|np.ndarray): Historical data points.
        forecast_days (int):           Horizon to forecast.

    Returns:
        dict: {forecast, lower_bound, upper_bound, model_params}

    Raises:
        ImportError: If statsmodels is not installed.
        Exception:   On model fitting or forecasting failure.
    """
    try:
        from statsmodels.tsa.arima.model import ARIMA

        data   = np.array(time_series, dtype=float)
        order  = (1, 1, 1)
        model  = ARIMA(data, order=order)
        fitted = model.fit()

        forecast_result = fitted.get_forecast(steps=forecast_days)
        forecast        = forecast_result.predicted_mean
        conf_int        = forecast_result.conf_int()

        logger.info("ARIMA forecast complete: %d days (AIC=%.2f)", forecast_days, fitted.aic)

        return {
            'forecast':     forecast.tolist(),
            'lower_bound':  conf_int.iloc[:, 0].tolist(),
            'upper_bound':  conf_int.iloc[:, 1].tolist(),
            'model_params': {
                'order': order,
                'aic':   float(fitted.aic),
                'bic':   float(fitted.bic),
            },
        }

    except Exception as exc:
        logger.error("ARIMA forecast error: %s", exc, exc_info=True)
        raise


def detect_anomalies(time_series, threshold=2.0):
    """
    Detect anomalies using a simple Z-score method.

    Points with |z| > threshold are flagged as anomalies.

    Args:
        time_series (list|np.ndarray): Time-series values.
        threshold (float):             Z-score threshold (default 2.0).

    Returns:
        dict: {anomaly_indices, z_scores, threshold, n_anomalies}
    """
    try:
        data    = np.array(time_series, dtype=float)
        mean    = np.mean(data)
        std     = np.std(data)

        if std == 0:
            # All values identical – no anomalies possible
            logger.info("detect_anomalies: std=0, no anomalies detected")
            return {
                'anomaly_indices': [],
                'z_scores':        np.zeros(len(data)).tolist(),
                'threshold':       threshold,
                'n_anomalies':     0,
            }

        z_scores  = np.abs((data - mean) / std)
        anomalies = np.where(z_scores > threshold)[0]

        logger.info("Anomaly detection: %d anomalies (threshold=%.1f)",
                    len(anomalies), threshold)

        return {
            'anomaly_indices': anomalies.tolist(),
            'z_scores':        z_scores.tolist(),
            'threshold':       threshold,
            'n_anomalies':     int(len(anomalies)),
        }

    except Exception as exc:
        logger.error("Anomaly detection error: %s", exc, exc_info=True)
        raise