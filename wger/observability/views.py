# -*- coding: utf-8 -*-

# This file is part of wger Workout Manager.
#
# wger Workout Manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# wger Workout Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Workout Manager.  If not, see <http://www.gnu.org/licenses/>.

# Django
from django.db import (
    connections,
    OperationalError,
)
from django.http import (
    HttpResponse,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt

# Third Party
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)


@csrf_exempt
def healthz(request):
    """
    Health check endpoint for PMOVES.AI observability.

    Returns:
        JsonResponse: {"status": "healthy"} with HTTP 200 if all services are operational
        JsonResponse: {"status": "degraded"} with HTTP 200 if integrations are down but core service is up
        JsonResponse: {"status": "unhealthy", "details": "..."} with HTTP 503 if core service issues detected
    """
    from wger.utils.integration_health import IntegrationHealth

    health_status = {
        'status': 'healthy',
        'checks': {},
        'integrations': {},
    }

    # Check database connectivity (core service)
    db_healthy = True
    db_error = None
    try:
        for db_name in connections:
            db_conn = connections[db_name]
            db_conn.ensure_connection()
    except OperationalError as e:
        db_healthy = False
        db_error = str(e)

    health_status['checks']['database'] = {
        'status': 'healthy' if db_healthy else 'unhealthy',
    }

    if not db_healthy:
        health_status['status'] = 'unhealthy'
        health_status['checks']['database']['error'] = db_error
        return JsonResponse(health_status, status=503)

    # Check external integrations (TensorZero, NATS, GPU Orchestrator)
    try:
        integration_health = IntegrationHealth()
        integrations = integration_health.get_status()

        all_healthy = all(
            integration['healthy'] for integration in integrations.values()
        )

        health_status['integrations'] = integrations

        if not all_healthy:
            health_status['status'] = 'degraded'

    except Exception as e:
        logger.warning(f"Integration health check failed: {e}")
        health_status['status'] = 'degraded'
        health_status['integrations'] = {
            'error': f"Integration health check failed: {str(e)}"
        }

    return JsonResponse(health_status, status=200)


@csrf_exempt
def metrics(request):
    """
    Prometheus metrics endpoint for PMOVES.AI observability.

    Returns:
        HttpResponse: Prometheus metrics in text format with content type
                     'text/plain; version=0.0.4; charset=utf-8'
    """
    # Check if metrics are exposed
    from django.conf import settings

    if not getattr(settings, 'EXPOSE_PROMETHEUS_METRICS', False):
        return JsonResponse(
            {'error': 'Prometheus metrics are not exposed'},
            status=403,
        )

    metrics_data = generate_latest()
    return HttpResponse(
        metrics_data,
        content_type=CONTENT_TYPE_LATEST,
    )
