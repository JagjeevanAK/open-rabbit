# Open Rabbit VS Code Extension

AI-powered code review in your IDE, triggered automatically on git commits.

## Features

- **Automatic Review on Commit** - Detects git commits and automatically triggers AI code review
- **Sidebar Panel** - Summary view showing review status, issue counts, and comment list
- **Floating Changes Window** - Detailed view with file-by-file breakdown, inline comments, and suggestions
- **Workspace-Scoped History** - Each project maintains its own review history
- **Apply Suggestions** - One-click apply for code suggestions

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/JagjeevanAK/open-rabbit.git
   cd open-rabbit/vscode-extension
   ```

2. Install dependencies:
   ```bash
   pnpm install
   ```

3. Compile the extension:
   ```bash
   pnpm run compile
   ```

4. Press `F5` in VS Code to launch the Extension Development Host

### From VSIX

```bash
code --install-extension open-rabbit-0.0.1.vsix
```

## Usage

### Automatic Review

1. Make changes to your code
2. Commit your changes
3. Open Rabbit will automatically trigger a review
4. View results in the sidebar or floating window

### Manual Review

1. Open the Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`)
2. Run "Open Rabbit: Review Current Changes"

### View Results

- **Sidebar**: Click the rabbit icon in the activity bar
- **Floating Window**: Run "Open Rabbit: Show Changes Window"

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `openRabbit.backendUrl` | `http://localhost:8080` | Backend API URL |
| `openRabbit.autoReviewOnCommit` | `true` | Auto-trigger review on commit |
| `openRabbit.showFloatingWindow` | `true` | Show floating window after review |
| `openRabbit.severityThreshold` | `info` | Minimum severity to display |
| `openRabbit.pollingInterval` | `2000` | Status polling interval (ms) |

## Requirements

- VS Code 1.108.0 or higher
- Git extension enabled
- Open Rabbit backend running (see main README)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    VS Code Extension                    │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Git Watcher │  │   Sidebar   │  │ Changes Panel   │  │
│  │ (Commit     │  │  Provider   │  │ (Floating       │  │
│  │  Detection) │  │  (WebView)  │  │  Window)        │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │
│         │                │                   │          │
│         └────────────────┼───────────────────┘          │
│                          │                              │
│                   ┌──────┴──────┐                       │
│                   │ API Client  │                       │
│                   └──────┬──────┘                       │
│                          │                              │
│                   ┌──────┴──────┐                       │
│                   │   State     │ (Workspace-scoped)    │
│                   │  Manager    │                       │
│                   └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   Open Rabbit Backend  │
              │   (FastAPI + Agents)   │
              └────────────────────────┘
```

## Development

### Build

```bash
pnpm run compile
```

### Watch Mode

```bash
pnpm run watch
```

### Type Check

```bash
pnpm run check-types
```

### Lint

```bash
pnpm run lint
```

## File Structure

```
src/
├── extension.ts          # Main entry point
├── types.ts              # TypeScript definitions
├── api/
│   └── apiClient.ts      # Backend API client
├── git/
│   └── gitWatcher.ts     # Git commit detection
├── state/
│   └── stateManager.ts   # Workspace-scoped state
└── views/
    ├── SidebarProvider.ts   # Sidebar webview
    └── ChangesPanel.ts      # Floating panel
```

## License

MIT
