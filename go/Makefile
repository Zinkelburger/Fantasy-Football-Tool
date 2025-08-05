.PHONY: all deps build test test-verbose test-coverage clean run fmt vet

all: test build

deps:
	go mod tidy

build: deps
	GOOS=linux GOARCH=amd64 go build -o draft_assist .

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
run: build
	./draft_assist

# Format code
fmt:
	go fmt ./...

# Run static analysis
vet: deps
	go vet ./...

# Check everything (useful before committing)
check: fmt vet test

clean:
	rm -f draft_assist coverage.out coverage.html

# Development workflow - run tests on file changes (requires entr)
watch:
	find . -name "*.go" | entr -c make test