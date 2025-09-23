.PHONY: all deps build test test-verbose test-coverage clean run fmt vet check watch release release-snapshot build-local package-local help

# Default target
all: test build

# Development dependencies
deps:
	go mod tidy

# Generate bundled Fyne resources
resource.go: logo.png
	fyne bundle -o resource.go logo.png

# Generate bundled font resource
font_resource.go: font/JetBrainsMonoNL-Regular.ttf
	fyne bundle -o font_resource.go font/JetBrainsMonoNL-Regular.ttf

# Local development build
build: deps resource.go font_resource.go
	GOOS=linux GOARCH=amd64 go build -o draft_assist .

# Quick local build for current platform
build-local: deps resource.go font_resource.go
	go build -o fantasy-football-tool .

# Create a local package (binary + analysis + csv) for testing
package-local: build-local
	@echo "Creating local package..."
	@mkdir -p dist/local
	@cp fantasy-football-tool dist/local/
	@cp -r analysis dist/local/
	@cp players.csv dist/local/
	@cp -r status dist/local/
	@echo "Local package created in dist/local/"
	@echo "To test: cd dist/local && ./fantasy-football-tool"

# Run all tests
test: deps
	go test -v ./...

# Run tests with verbose output and race detection
test-verbose: deps
	go test -v -race ./...

# Run tests with coverage report
test-coverage: deps
	go test -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report generated: coverage.html"

# Run the application (requires OPENAI_API_KEY env var)
run: build-local
	./fantasy-football-tool

# Format code
fmt:
	go fmt ./...

# Run static analysis
vet: deps
	go vet ./...

# Check everything (useful before committing)
check: fmt vet test

# Development workflow - run tests on file changes (requires entr)
watch:
	find . -name "*.go" | entr -c make test

# === GoReleaser-based releases ===

# Full release (requires git tag and clean working directory)
# Usage: git tag v1.0.0 && make release
release: deps
	@echo "Building release with GoReleaser..."
	@if [ -z "$$(git tag --points-at HEAD)" ]; then \
		echo "Error: No git tag found on current commit. Create a tag first: git tag v1.0.0"; \
		exit 1; \
	fi
	~/go/bin/goreleaser release --clean

# Snapshot release (for testing, doesn't require git tag)
release-snapshot: deps
	@echo "Building snapshot release with GoReleaser..."
	~/go/bin/goreleaser release --snapshot --clean
	@echo ""
	@echo "Snapshot release created in dist/ directory"
	@echo "Archives: dist/*.tar.gz, dist/*.zip"
	@echo "Packages: dist/*.deb, dist/*.rpm"

# Check GoReleaser configuration
check-release: deps
	~/go/bin/goreleaser check

# === Legacy release targets (kept for compatibility) ===

# Simple release build for current platform only (using old method)
release-simple: deps resource.go font_resource.go
	@echo "Building simple release for current platform..."
	@mkdir -p releases/binaries releases/archives
	@CGO_ENABLED=1 go build -ldflags "-s -w" -a -installsuffix cgo \
		-o releases/binaries/fantasy-football-tool .
	@echo "Creating release archive..."
	@cp -r analysis releases/binaries/
	@cp players.csv releases/binaries/
	@cd releases/binaries && \
		tar -czf ../archives/fantasy-football-tool-$(shell go env GOOS)-$(shell go env GOARCH).tar.gz \
		fantasy-football-tool analysis players.csv
	@rm -rf releases/binaries/analysis releases/binaries/players.csv
	@echo "Release archive created: releases/archives/fantasy-football-tool-$(shell go env GOOS)-$(shell go env GOARCH).tar.gz"

# Clean all build artifacts
clean:
	rm -f draft_assist fantasy-football-tool coverage.out coverage.html resource.go font_resource.go
	rm -rf releases/ dist/

# Help target
help:
	@echo "Fantasy Football Tool - Build System"
	@echo ""
	@echo "Development:"
	@echo "  make build-local     Build for current platform"
	@echo "  make package-local   Create local test package" 
	@echo "  make run             Build and run locally"
	@echo "  make test            Run tests"
	@echo "  make check           Format, lint, and test"
	@echo "  make watch           Run tests on file changes"
	@echo ""
	@echo "Releases (GoReleaser):"
	@echo "  make release-snapshot  Build all platforms/packages (no git tag needed)"
	@echo "  make release          Full release (requires git tag)"
	@echo "  make check-release    Validate GoReleaser config"
	@echo ""
	@echo "Legacy:"
	@echo "  make build           Build 'draft_assist' for Linux"
	@echo "  make release-simple  Simple release for current platform"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           Remove all build artifacts"
