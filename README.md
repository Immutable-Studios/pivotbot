# Market Structure Trading Bot

A Python-based trading bot that monitors stock prices and sends Discord alerts when prices cross pivot levels. This bot uses the Alpaca API for market data and posts beautiful embed messages to a Discord channel when pivot levels are crossed.

## Features

- **Real-time Stock Monitoring**: Tracks multiple stocks simultaneously
- **Pivot Point Calculations**: Automatically calculates daily pivot points (Pivot, R1, S1, R2, S2)
- **Discord Notifications**: Sends rich embed messages to Discord channel when prices cross pivot levels
- **Daily Pivot Updates**: Posts daily pivot level summaries to Discord
- **Dockerized**: Easy deployment with Docker and docker-compose
- **Configurable**: Environment-based configuration
- **Anti-spam**: Cooldown periods to prevent duplicate alerts

## Quick Start

### Prerequisites

- Docker and Docker Compose installed on your Linux system
- Alpaca Trading account (free paper trading account works)
- Discord server with a channel called "pivots" (or your preferred name)
- Discord bot token

### 1. Get Your Alpaca API Keys

1. Sign up for a free account at [Alpaca Markets](https://alpaca.markets/)
2. Navigate to your dashboard and create API keys
3. Use paper trading keys for testing (recommended)

### 2. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section and click "Add Bot"
4. Copy the bot token (you'll need this for the .env file)
5. Under "Privileged Gateway Intents", enable "Message Content Intent"
6. Go to "OAuth2" > "URL Generator"
7. Select "bot" scope and "Send Messages" + "Embed Links" permissions
8. Use the generated URL to invite the bot to your Discord server
9. Create a channel called "pivots" (or your preferred name)

### 3. Clone and Setup

```bash
# Clone the repository (or copy the files to your server)
git clone <your-repo-url>
cd marketstructure

# Run the setup script
./setup.sh

# Edit the .env file with your credentials
nano .env
```

### 4. Configure Environment Variables

Edit the `.env` file with your credentials:

```bash
# Alpaca API Configuration (REQUIRED)
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_API_SECRET=your_alpaca_api_secret_here

# Alpaca API Base URL (OPTIONAL - defaults to paper trading)
ALPACA_BASE_URL=https://paper-api.alpaca.markets/v2

# Discord Bot Configuration (REQUIRED)
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL=pivots

# Trading Configuration (OPTIONAL - has defaults)
STOCKS=AAPL,MSFT,TSLA
PIVOT_TIMEFRAME=1Day
CROSSING_THRESHOLD=0.01
ALERT_COOLDOWN=300
```

**Required Variables:**
- `ALPACA_API_KEY`: Your Alpaca API key
- `ALPACA_API_SECRET`: Your Alpaca API secret
- `DISCORD_BOT_TOKEN`: Your Discord bot token

**Optional Variables:**
- `ALPACA_BASE_URL`: API endpoint (defaults to paper trading)
- `DISCORD_CHANNEL`: Discord channel name (defaults to "pivots")
- `STOCKS`: Comma-separated list of stocks to monitor
- `CROSSING_THRESHOLD`: Price proximity to pivot level (default: 0.01)
- `ALERT_COOLDOWN`: Seconds between duplicate alerts (default: 300)

### 5. Deploy with Docker Compose

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

## Manual Installation (Alternative)

If you prefer not to use Docker:

```bash
# Install Python 3.11+ and pip
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables and run
export ALPACA_API_KEY="your_key"
export ALPACA_API_SECRET="your_secret"
export DISCORD_BOT_TOKEN="your_discord_token"
python main.py
```

## How It Works

1. **Initialization**: The bot connects to Discord and fetches historical data for configured stocks
2. **Pivot Calculation**: Calculates daily pivot points and posts them to Discord
3. **Real-time Monitoring**: Connects to Alpaca's WebSocket feed for live price updates
4. **Discord Alerts**: When a stock price comes within the threshold of a pivot level, sends a rich embed to Discord
5. **Daily Updates**: Pivot levels are recalculated daily at market close with summary posted to Discord

### Discord Alert Example

When an alert is triggered, a rich embed message is posted to your Discord channel:

🚀 **Pivot Level Alert**
- **Symbol**: AAPL
- **Pivot Level**: R1  
- **Price**: $150.25
- **Description**: ⬆️ Price is approaching resistance level R1

The bot also posts daily pivot level summaries showing all calculated levels for your monitored stocks.

## Configuration Options

### Stock Selection
Modify the `STOCKS` environment variable to monitor different stocks:
```bash
STOCKS=AAPL,MSFT,TSLA,GOOGL,AMZN
```

### Sensitivity Settings
- `CROSSING_THRESHOLD`: How close to pivot level triggers alert (default: 0.01)
- `ALERT_COOLDOWN`: Minimum seconds between alerts for same level (default: 300)

### Timeframes
Currently supports daily pivot calculations (`1Day`). The bot recalculates pivots every 24 hours.

## Monitoring and Logs

```bash
# View real-time logs
docker-compose logs -f trading-bot

# Check container status
docker-compose ps

# Restart the bot
docker-compose restart trading-bot
```

## Security Notes

- ⚠️ **Never commit your `.env` file to version control**
- Use paper trading API keys for testing
- Consider using environment variable injection for production
- Keep your Discord bot token secure and never share it publicly
- Consider limiting Discord bot permissions to only what's needed

## Troubleshooting

### Common Issues

1. **API Authentication Errors**
   - Verify your API keys are correct
   - Ensure you're using the right base URL (paper vs live)

2. **WebSocket Connection Issues**
   - Check your internet connection
   - Verify Alpaca service status

3. **Discord Bot Issues**
   - Verify your Discord bot token is correct
   - Ensure the bot has been invited to your server
   - Check that the bot has "Send Messages" and "Embed Links" permissions
   - Verify the channel name matches DISCORD_CHANNEL setting
   - Make sure "Message Content Intent" is enabled in Discord Developer Portal

4. **Bot Not Finding Channel**
   - Ensure channel name exactly matches DISCORD_CHANNEL (default: "pivots")
   - Bot must be a member of the server containing the channel
   - Channel must be a text channel, not voice channel

### Debug Mode

To run with verbose logging:

```bash
# Add to your .env file
LOG_LEVEL=DEBUG

# Or run directly with Docker
docker-compose up
```

## Development

### Project Structure
```
marketstructure/
├── main.py              # Main trading bot application
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
├── docker-compose.yml  # Docker Compose setup
├── .env.example        # Environment template
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

### Adding Features

The bot is designed to be easily extensible. Key areas for customization:

- **Pivot Calculations**: Modify `calculate_pivot_points()` function
- **Alert Logic**: Update `check_pivot_crossing()` function
- **Additional Indicators**: Add new technical analysis functions

## License

This project is provided as-is for educational purposes. Use at your own risk in live trading environments.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Docker and application logs
3. Verify your Alpaca API configuration 