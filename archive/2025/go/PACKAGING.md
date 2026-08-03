# Fantasy Football Tool - Packaging Guide

This project uses **GoReleaser** for systematic, clean packaging and distribution. It creates multiple package formats including archives, .deb packages, and .rpm packages.

## Quick Start

### Development
```bash
# Build and test locally
make build-local
make package-local  # Creates dist/local/ with everything you need to test

# Run tests
make test
make check  # Format, lint, and test
```

### Create Release Packages
```bash
# Create snapshot packages (no git tag required)
make release-snapshot

# Full release (requires git tag)
git tag v1.0.0
make release
```

## What Gets Packaged

Each distribution includes:
- **Binary**: `fantasy-football-tool` executable 
- **Analysis Files**: Complete `analysis/` directory with all player .md files
- **Player Data**: `players.csv` with rankings and stats
- **Status Files**: `status/` directory for runtime state
- **Documentation**: README.md

## Package Formats Created

### Archives (Portable)
- **Linux**: `fantasy-football-tool-Linux-x86_64.tar.gz`
- Extract anywhere and run `./fantasy-football-tool`

### Linux Packages (System Installation)
- **Debian/Ubuntu**: `fantasy-football-tool-VERSION-x86_64.deb`
- **RHEL/Fedora/CentOS**: `fantasy-football-tool-VERSION-x86_64.rpm`

#### Package Installation Paths
```
/usr/bin/fantasy-football-tool                    # Main executable
/usr/share/fantasy-football-tool/analysis/        # Player analysis files
/usr/share/fantasy-football-tool/players.csv      # Player data
/usr/share/fantasy-football-tool/status/          # Status files
/etc/fantasy-football-tool/                       # Config directory
/var/lib/fantasy-football-tool/                   # User data directory
```

## Installation Examples

### Quick Install (Any Linux)
```bash
# Download and run (replace URL with actual release)
curl -L https://github.com/USER/REPO/releases/download/v1.0.0/fantasy-football-tool-Linux-x86_64.tar.gz | tar xz
cd fantasy-football-tool-Linux-x86_64/
./fantasy-football-tool
```

### System Package Install

#### Debian/Ubuntu
```bash
wget https://github.com/USER/REPO/releases/download/v1.0.0/fantasy-football-tool-1.0.0-x86_64.deb
sudo dpkg -i fantasy-football-tool-1.0.0-x86_64.deb
fantasy-football-tool
```

#### RHEL/Fedora/CentOS
```bash
wget https://github.com/USER/REPO/releases/download/v1.0.0/fantasy-football-tool-1.0.0-x86_64.rpm
sudo rpm -i fantasy-football-tool-1.0.0-x86_64.rpm
fantasy-football-tool
```

## Cross-Platform Notes

Currently configured for **Linux x86_64** only due to CGO/Fyne cross-compilation complexity.

For other platforms:
- **Windows/macOS**: Run GoReleaser natively on each platform
- **ARM64**: Requires cross-compilation toolchain setup

## GoReleaser Configuration

The `.goreleaser.yaml` file defines:
- **Build targets**: Linux x86_64 (expandable)
- **Archive formats**: tar.gz (Linux), zip (Windows)
- **Package formats**: .deb and .rpm for Linux
- **File inclusion**: Automatically packages analysis/, players.csv, status/
- **Installation paths**: Standard Linux filesystem hierarchy

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make build-local` | Build for current platform |
| `make package-local` | Create local test package |
| `make release-snapshot` | Build all packages (no git tag needed) |
| `make release` | Full release (requires git tag) |
| `make check-release` | Validate GoReleaser config |
| `make clean` | Remove all build artifacts |
| `make help` | Show all available targets |

## Benefits of This Approach

✅ **Clean & Systematic**: No more complex Makefile with repetitive code  
✅ **Multiple Formats**: Archives, .deb, .rpm all from one command  
✅ **Proper Linux Integration**: System packages with correct paths  
✅ **Checksums**: Automatic verification files  
✅ **Metadata**: Proper package descriptions and dependencies  
✅ **Scalable**: Easy to add more platforms/formats later  

## vs. Old Approach

**Before**: 175-line Makefile with repetitive cross-compilation logic  
**After**: Clean Makefile + GoReleaser config that handles everything systematically

The old Makefile is preserved as `Makefile.old` for reference.
