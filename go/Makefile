.PHONY: all deps build

all: build

deps:
	go mod tidy

build: deps
	GOOS=linux GOARCH=amd64 go build -o charmui .

clean:
	rm -f charmui