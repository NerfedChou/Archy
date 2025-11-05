# Archy

Archy is a local AI assistant designed for Arch Linux. It runs locally using tmux + foot for a single, reusable terminal that Archy can read, summarize, and continue using across commands. Provider: Google Gemini.

## Table of Contents
1. Installation
2. Features
3. Usage
4. Troubleshooting
5. Contributing

## Installation
1. Prerequisites:
   ```bash
   sudo pacman -S --needed python python-pip curl
   ```
2. Clone the repository:
   ```bash
   git clone https://github.com/NerfedChou/Archy.git
   cd Archy
   ```
3. Configure environment (create `.env`):
   ```ini
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   GEMINI_HOST=https://generativelanguage.googleapis.com/v1beta/openai/
   MODEL_PROVIDER=gemini
   ```
4. Install:
   ```bash
   ./install.sh
   ```
5. Quick test:
   ```bash
   archy "what is my working directory?"
   archy
   ```

## Features
- Single, reusable terminal session (tmux backend, foot frontend)
- Real-time command execution with output capture and summaries
- Personality-driven responses (casual, helpful, a little witty)
- Local-first design using your system tools

## Usage
```bash
# Interactive chat mode
archy

# Single question mode
archy "what is my working directory?"
```

### Notes on the terminal
- Archy opens/attaches a foot window to a persistent tmux session.
- If you close foot, the tmux session stays alive; asking Archy to run a command will re-open foot and reuse the same session.
- You can also ask Archy to close the tmux session explicitly: type "close session".

## Troubleshooting
- Archy CLI not found:
  ```bash
  which archy
  ls -l /usr/local/bin/archy
  ```
- Gemini API key issues:
  - Ensure GEMINI_API_KEY is set in `.env` or `.api`.
  - Check network connectivity.

## Contributing
1. Fork the repository.
2. Create a branch for your change.
3. Commit and push.
4. Open a pull request with a description of your changes.

Thank you for using Archy! We hope it enhances your Arch Linux experience.