# Archy

Archy is a local AI assistant designed specifically for Arch Linux users. This documentation aims to provide comprehensive information about Archy, including installation, features, usage, and troubleshooting.

## Table of Contents
1. [Installation](#installation)
2. [Features](#features)
3. [Usage](#usage)
4. [Troubleshooting](#troubleshooting)
5. [Contributing](#contributing)

## Installation
To install Archy, follow these steps:

1. **Prerequisites**: Ensure you have Python 3 and curl installed:
   ```bash
   sudo pacman -S python python-pip curl
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/NerfedChou/Archy.git
   cd Archy
   ```

3. **Configure environment** (optional):
   Edit `.env` file to set your Groq API key and other settings:
   ```bash
   # Groq API Configuration
   GROQ_API_KEY=your_groq_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   GROQ_HOST=https://api.groq.com/openai/v1

   # MCP Server Configuration
   MCP_SERVER=http://localhost:8000
   ```

4. **Run the installation script**:
   ```bash
   ./install.sh
   ```

   This will:
   - Set up a native MCP (Machine Command Processor) server at `/opt/mcp`
   - Create a systemd service to run MCP on boot
   - Install CLI tools to `/usr/local/bin`
   - Configure environment variables

5. **Verify installation**:
   ```bash
   systemctl status mcp.service  # Check MCP service
   archy "what is my working directory?"  # Test Archy
   ```

## Features
- **Natural Language Processing**: Interact with your Archy assistant using natural language.
- **System Management**: Perform various system management tasks such as package installation and updates.
- **Real-time Command Execution**: Execute system commands directly through the MCP server.
- **Customization**: Users can customize the functionalities based on their preferences.
- **Community Support**: Engage with the Archy community for support and sharing tips.

## Usage
To start using Archy, launch it from your terminal:

```bash
# Interactive chat mode
archy

# Single question mode
archy "what is my working directory?"
archy "update my system"
archy "show me the available tools"
```

### Available Commands
- `archy` - Launch interactive chat mode
- `archy "question"` - Ask a single question
- `archy chat` - Same as `archy` (interactive mode)
- `archy help` - Show help information

### MCP Service Management
```bash
# Check MCP service status
systemctl status mcp.service

# Restart MCP service
sudo systemctl restart mcp.service

# View MCP logs
journalctl -u mcp.service -f
```

## Troubleshooting
If you encounter issues, try the following:

- **MCP Server not responding**:
  ```bash
  sudo systemctl restart mcp.service
  curl http://localhost:8000/system_info/
  ```

- **Archy not working**:
  - Check if MCP service is running: `systemctl status mcp.service`
  - Verify CLI tools: `which archy`
  - Check environment: `cat .env`

- **API Key issues**:
  - Ensure your Groq API key is set in `.env`
  - Check API key validity at https://console.groq.com/

- **Permission issues**:
  - MCP runs as your user, ensure proper permissions for system commands

- **General troubleshooting**:
  - Ensure Python 3 and pip are installed
  - Check systemd services: `systemctl --failed`
  - View logs: `journalctl -u mcp.service --no-pager -n 50`

For more help, check the [GitHub Issues](https://github.com/NerfedChou/Archy/issues) or community forums.

## Contributing
We welcome contributions from the community. To contribute:
1. Fork the repository.
2. Create a new branch for your feature or fix.
3. Make your changes and commit them.
4. Push your changes to your fork.
5. Submit a pull request with a description of your changes.

Thank you for using Archy! We hope it enhances your Arch Linux experience.