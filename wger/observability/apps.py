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
from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    """
    Configuration for the observability app.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wger.observability'
    verbose_name = 'Observability'

    def ready(self):
        """
        Perform initialization when Django starts.

        - Import signal handlers to register NATS event publishers
        - Logs integration health status at startup
        """
        # Import signal handlers to register them
        # This must happen at import time, not at runtime
        import wger.observability.signals  # noqa: F401

        # Only log in the main process to avoid duplicate logs in reload scenarios
        import os
        run_main = os.environ.get('RUN_MAIN', None)

        if run_main is None:  # Only run during initial startup
            try:
                from wger.utils.integration_health import IntegrationHealth
                health_check = IntegrationHealth()
                integrations = health_check.get_status()

                print("[STARTUP] Integration Status:")
                for name, status in integrations.items():
                    health_str = "✓" if status["healthy"] else "✗"
                    print(f"  {health_str} {name}: {status['url']}")
            except Exception as e:
                print(f"[STARTUP] Integration health check failed: {e}")
