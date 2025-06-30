#!/bin/bash

# Market Structure Trading Bot Setup Script
echo "🚀 Market Structure Trading Bot Setup"
echo "======================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first:"
    echo "   curl -fsSL https://get.docker.com -o get-docker.sh"
    echo "   sudo sh get-docker.sh"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first:"
    echo "   sudo apt install docker-compose"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env << 'EOF'
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
EOF
    echo "✅ Created .env file"
else
    echo "✅ .env file already exists"
fi

# Create logs directory
mkdir -p logs
echo "✅ Created logs directory"

echo ""
echo "⚠️  IMPORTANT: Before starting the bot, you need to:"
echo "   1. Edit the .env file with your Alpaca API credentials"
echo "   2. Create a Discord bot and get its token"
echo "   3. Add your Discord bot token to the .env file"
echo "   4. Invite the bot to your Discord server"
echo "   5. Create a channel called 'pivots' (or change DISCORD_CHANNEL)"
echo ""
echo "🤖 To create a Discord bot:"
echo "   1. Go to https://discord.com/developers/applications"
echo "   2. Create a new application"
echo "   3. Go to 'Bot' section and create a bot"
echo "   4. Copy the bot token to your .env file"
echo "   5. Go to 'OAuth2' > 'URL Generator'"
echo "   6. Select 'bot' scope and 'Send Messages' permission"
echo "   7. Use the generated URL to invite bot to your server"
echo ""
echo "📝 To edit your configuration:"
echo "   nano .env"
echo ""
echo "🚀 To start the bot:"
echo "   docker-compose up -d"
echo ""
echo "📊 To view logs:"
echo "   docker-compose logs -f"
echo ""
echo "🛑 To stop the bot:"
echo "   docker-compose down"
echo ""
echo "🎯 Get your Alpaca API keys at: https://alpaca.markets/"
echo ""
echo "Setup complete! 🎉" 