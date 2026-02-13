# PMOVES-Health-wger Makefile - Hardened Architecture
# Dual-mode operation: standalone or docked to PMOVES.AI

SHELL := /bin/bash
.SHELLFLAGS := -ec

# Docker compose command
COMPOSE ?= $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

# Image names
DOCKERHUB_IMAGE := powerfulmoves/pmoves-health-wger
GHCR_IMAGE := ghcr.io/powerfulmoves/pmoves-health-wger
VERSION ?= pmoves-latest

# Build platforms
PLATFORMS := linux/amd64,linux/arm64

.PHONY: help up up-nginx up-postgres down restart logs build push status clean install check test db-migrate

help:
	@echo "PMOVES-Health-wger Commands"
	@echo "==========================="
	@echo "  make up           - Start wger with SQLite"
	@echo "  make up-nginx     - Start wger with nginx frontend"
	@echo "  make up-postgres  - Start wger with PostgreSQL"
	@echo "  make down         - Stop wger"
	@echo "  make restart      - Restart wger"
	@echo "  make logs         - View logs"
	@echo "  make status       - Check service status"
	@echo "  make build        - Build Docker image"
	@echo "  make push         - Build and push multi-arch image"
	@echo "  make clean        - Remove containers and volumes"
	@echo "  make install      - Setup environment"
	@echo "  make check        - Verify configuration"
	@echo "  make db-migrate   - Run database migrations"

# Check environment
check:
	@echo "Checking environment..."
	@docker --version > /dev/null 2>&1 || { echo "✗ Docker not found"; exit 1; }
	@$(COMPOSE) version > /dev/null 2>&1 || { echo "✗ Docker Compose not found"; exit 1; }
	@test -f .env || { echo "✗ .env file not found. Run 'make install'"; exit 1; }
	@echo "✓ Environment OK"

# Install/setup
install: check
	@echo "Setting up PMOVES-Health-wger..."
	@test -f .env || cp .env.example .env
	@test -f .env.local || cp .env.local.example .env.local
	@echo "✓ Configuration files created"
	@echo "✓ Setup complete. Edit .env and .env.local files to configure."

# Start service (SQLite)
up: check
	@echo "Starting PMOVES-Health-wger with SQLite..."
	@$(COMPOSE) up -d
	@echo "✓ wger started"
	@echo "  Web UI: http://localhost:8000"

# Start service (with nginx)
up-nginx: check
	@echo "Starting PMOVES-Health-wger with nginx..."
	@$(COMPOSE) --profile nginx up -d
	@echo "✓ wger started with nginx"
	@echo "  Web UI: http://localhost:80"

# Start service (PostgreSQL)
up-postgres: check
	@echo "Starting PMOVES-Health-wger with PostgreSQL..."
	@$(COMPOSE) --profile postgres up -d
	@echo "✓ wger started with PostgreSQL"
	@echo "  Web UI: http://localhost:8000"

# Stop service
down:
	@echo "Stopping PMOVES-Health-wger..."
	@$(COMPOSE) --profile nginx --profile postgres down
	@echo "✓ wger stopped"

# Restart service
restart: down
	@$(MAKE) -s up

# View logs
logs:
	@$(COMPOSE) logs -f web

# Check status
status:
	@echo "PMOVES-Health-wger Status:"
	@$(COMPOSE) ps

# Build image
build:
	@echo "Building PMOVES-Health-wger image..."
	@docker build \
		-t $(DOCKERHUB_IMAGE):$(VERSION) \
		-t $(GHCR_IMAGE):$(VERSION) \
		.
	@echo "✓ Build complete"
	@echo "  Images tagged:"
	@echo "    - $(DOCKERHUB_IMAGE):$(VERSION)"
	@echo "    - $(GHCR_IMAGE):$(VERSION)"

# Build and push multi-arch
push: buildx-prepare
	@echo "Building and pushing multi-arch image..."
	@docker buildx build \
		--platform $(PLATFORMS) \
		--progress=plain \
		-t $(DOCKERHUB_IMAGE):$(VERSION) \
		-t $(GHCR_IMAGE):$(VERSION) \
		--push \
		.
	@echo "✓ Multi-arch push complete"

# Buildx helpers
buildx-prepare:
	@docker buildx inspect multi-platform-builder >/dev/null 2>&1 || \
		docker buildx create --use --name multi-platform-builder --driver docker-container
	@docker buildx use multi-platform-builder

# Clean up
clean:
	@echo "Cleaning up PMOVES-Health-wger..."
	@$(COMPOSE) --profile nginx --profile postgres down -v
	@docker volume rm ${VOLUME_PREFIX:-wger}_media ${VOLUME_PREFIX:-wger}_static ${VOLUME_PREFIX:-wger}_db 2>/dev/null || true
	@echo "✓ Cleanup complete"

# Database migrations
db-migrate:
	@echo "Running database migrations..."
	@$(COMPOSE) exec web python manage.py migrate
	@echo "✓ Migrations complete"

# Load initial data
db-load-data:
	@echo "Loading initial data..."
	@$(COMPOSE) exec web python manage.py load-exercises
	@$(COMPOSE) exec web python manage.py load-ingredients
	@echo "✓ Initial data loaded"

# Create admin user
create-admin:
	@echo "Creating admin user..."
	@$(COMPOSE) exec web python manage.py createsuperuser
	@echo "✓ Admin user creation prompt shown"

# Health check
test:
	@echo "Testing PMOVES-Health-wger..."
	@curl -fSs http://localhost:8000 > /dev/null && echo "✓ Health check passed" || echo "✗ Health check failed"
