# Fantasy Football Tool - GUI Version

A modern GUI application for fantasy football draft assistance powered by ChatGPT.

## Features
- **Real-time player list** with automatic refresh every 3 seconds
- **ChatGPT integration** for draft recommendations based on your team and notes
- **Manual refresh** to update player data on demand
- **Keyboard shortcuts** for power users
- **Modern GUI** with split-panel layout

## Controls
- **Click "Query ChatGPT" button** or press **Q**: Get AI draft recommendations
- **Click "Manual Refresh" button** or press **R**: Refresh player data immediately  
- **Press Esc**: Quit the application

## Building and Running

### Prerequisites
On Linux (Fedora/RHEL):
```bash
sudo dnf install -y libX11-devel libXrandr-devel libXxf86vm-devel libXi-devel libXcursor-devel libXinerama-devel mesa-libGL-devel
```

### Build
```bash
go mod tidy
go build -o fantasy-tool
```

### Run
```bash
./fantasy-tool
```

## Requirements
- Go 1.23.0 or later
- OpenAI API key (configured via settings UI or environment variable)
- Player data file (`combined_with_depth.csv`)
- Player analysis notes in `analysis/` directory

## Configuration
The application automatically handles configuration in the following priority order:

1. **Settings UI**: Configure OpenAI API key and Ollama settings through the gear icon in the application
2. **Environment Variables**: Set `OPENAI_API_KEY`, `USE_LOCAL_LLM`, `OLLAMA_MODEL`, `OLLAMA_ENDPOINT`
3. **Default Values**: Built-in defaults for Ollama configuration

When you save settings through the UI, they are automatically saved to a `.env` file for persistence.

## Go Installation
If you need to install Go:
```bash
rm -rf /usr/local/go && tar -C /usr/local -xzf go1.24.4.linux-amd64.tar.gz
```
Download from: https://go.dev/dl/
