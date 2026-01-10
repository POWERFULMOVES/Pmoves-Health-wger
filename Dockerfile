# PMOVES-Health-wger - Hardened Architecture Dockerfile
# Extends upstream wger with PMOVES branded defaults

# Use upstream wger image as base
FROM ghcr.io/wger/wger:latest

# PMOVES branded labels
LABEL maintainer="PMOVES.AI <ops@cataclysmstudios.com>"
LABEL description="PMOVES-enhanced wger fitness tracker"
LABEL org.pmoves.version="1.0.0-hardened"
LABEL org.pmoves.mode="standalone-docked"

# Set working directory
WORKDIR /home/wger/

# PMOVES branded default user (wger:wger in container, mapped to 65532:65532)
USER wger

# Health check (wger uses Django management command from /home/wger/src)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD cd /home/wger/src && python manage.py check --deploy || exit 1

# Expose web UI
EXPOSE 8000

# Use upstream wger entrypoint
# The upstream image defines ENTRYPOINT, so we don't override CMD
# This ensures compatibility with upstream updates
