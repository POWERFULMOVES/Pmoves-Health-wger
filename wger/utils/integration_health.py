"""
Integration health checker for PMOVES services (Django version).

This module provides synchronous health checks for external service dependencies
used in standalone mode (TensorZero, NATS, GPU Orchestrator).
"""

import os
import logging
from typing import Dict
from django.conf import settings

logger = logging.getLogger(__name__)


class IntegrationHealth:
    """Integration health checker for PMOVES services (Django)."""

    def __init__(self):
        """Initialize health checker with configuration from environment."""
        self.tensorzero_url = os.getenv(
            'TENSORZERO_BASE_URL',
            'http://tensorzero-gateway:3030'
        ).rstrip('/')
        self.nats_url = os.getenv('NATS_URL', 'nats://nats:4222')
        self.gpu_orchestrator_url = os.getenv('GPU_ORCHESTRATOR_URL')

    def check_tensorzero(self, timeout: float = 2.0) -> bool:
        """
        Check if TensorZero Gateway is reachable.

        Args:
            timeout: Request timeout in seconds

        Returns:
            True if TensorZero is healthy, False otherwise
        """
        try:
            import requests
            resp = requests.get(
                f"{self.tensorzero_url}/health",
                timeout=timeout
            )
            is_healthy = resp.status_code == 200
            if is_healthy:
                logger.debug(f"TensorZero health check passed: {self.tensorzero_url}")
            else:
                logger.warning(f"TensorZero returned status {resp.status_code}")
            return is_healthy
        except Exception as e:
            logger.warning(f"TensorZero health check failed: {e}")
            return False

    def check_nats(self, timeout: float = 2.0) -> bool:
        """
        Check if NATS is reachable.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if NATS is reachable, False otherwise
        """
        try:
            import nats
            import asyncio

            # Use asyncio.run to call async nats.connect in sync context
            try:
                nc = asyncio.run(nats.connect(
                    self.nats_url,
                    timeout=timeout,
                    connect_timeout=timeout
                ))
                asyncio.run(nc.flush())
                asyncio.run(nc.close())
                logger.debug(f"NATS health check passed: {self.nats_url}")
                return True
            except Exception as e:
                logger.warning(f"NATS health check failed: {e}")
                return False
        except ImportError:
            logger.warning("nats-py not available, cannot check NATS")
            return False
        except Exception as e:
            logger.warning(f"NATS health check failed: {e}")
            return False

    def check_gpu_orchestrator(self, timeout: float = 2.0) -> bool:
        """
        Check if GPU Orchestrator is reachable (optional).

        Args:
            timeout: Request timeout in seconds

        Returns:
            True if GPU Orchestrator is healthy, False if not or not configured
        """
        if not self.gpu_orchestrator_url:
            logger.debug("GPU Orchestrator not configured, skipping check")
            return False  # Not configured

        try:
            import requests
            resp = requests.get(
                f"{self.gpu_orchestrator_url}/healthz",
                timeout=timeout
            )
            is_healthy = resp.status_code == 200
            if is_healthy:
                logger.debug(f"GPU Orchestrator health check passed: {self.gpu_orchestrator_url}")
            else:
                logger.warning(f"GPU Orchestrator returned status {resp.status_code}")
            return is_healthy
        except Exception as e:
            logger.warning(f"GPU Orchestrator health check failed: {e}")
            return False

    def get_status(self) -> Dict[str, Dict]:
        """
        Get all integration health statuses.

        Returns:
            Dict mapping integration names to their health status and URLs
        """
        return {
            "tensorzero": {
                "healthy": self.check_tensorzero(),
                "url": self.tensorzero_url
            },
            "nats": {
                "healthy": self.check_nats(),
                "url": self.nats_url
            },
            "gpu_orchestrator": {
                "healthy": self.check_gpu_orchestrator(),
                "url": self.gpu_orchestrator_url
            }
        }
