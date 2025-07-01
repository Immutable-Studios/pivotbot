import alpaca_trade_api as tradeapi
import pandas as pd
import requests
import websocket
import json
import threading
import time
import os
import asyncio
import discord
from datetime import datetime
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()

API_KEY = os.getenv('ALPACA_API_KEY')
API_SECRET = os.getenv('ALPACA_API_SECRET')
BASE_URL = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets/v2')
DATA_URL = 'https://data.alpaca.markets/v2'
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL = os.getenv('DISCORD_CHANNEL', 'pivots')
STOCKS = os.getenv('STOCKS', 'AAPL,MSFT,TSLA').split(',')
PIVOT_TIMEFRAME = os.getenv('PIVOT_TIMEFRAME', '1Day')
CROSSING_THRESHOLD = float(os.getenv('CROSSING_THRESHOLD', '0.01'))
ALERT_COOLDOWN = int(os.getenv('ALERT_COOLDOWN', '300'))
REAL_TIME_DEBUG = os.getenv('REAL_TIME_DEBUG', 'true').lower() == 'true'

if not API_KEY or not API_SECRET:
    raise ValueError("ALPACA_API_KEY and ALPACA_API_SECRET environment variables are required")
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable is required")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL)

pivot_levels = {stock: {} for stock in STOCKS}
last_alert = {stock: {} for stock in STOCKS}

intents = discord.Intents.default()
intents.message_content = True
discord_client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(discord_client)
discord_channel_obj = None

@discord_client.event
async def on_ready():
    global discord_channel_obj
    print(f'{discord_client.user} has connected to Discord!')
    
    print(f"🔍 Bot is in {len(discord_client.guilds)} server(s):")
    for guild in discord_client.guilds:
        print(f"  📍 Server: '{guild.name}' (ID: {guild.id})")
        print(f"     👥 Members: {guild.member_count}")
        text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
        print(f"     📝 Text channels ({len(text_channels)}):")
        for channel in text_channels:
            permissions = channel.permissions_for(guild.me)
            can_send = permissions.send_messages
            can_embed = permissions.embed_links
            print(f"       - #{channel.name} (ID: {channel.id}) - Send: {can_send}, Embed: {can_embed}")
    
    print(f"🎯 Looking for channel named: '{DISCORD_CHANNEL}'")
    
    for guild in discord_client.guilds:
        for channel in guild.channels:
            if channel.name == DISCORD_CHANNEL and isinstance(channel, discord.TextChannel):
                permissions = channel.permissions_for(guild.me)
                if not permissions.send_messages:
                    print(f"❌ Found channel #{channel.name} but missing Send Messages permission!")
                    continue
                if not permissions.embed_links:
                    print(f"❌ Found channel #{channel.name} but missing Embed Links permission!")
                    continue
                
                discord_channel_obj = channel
                print(f'✅ Found Discord channel: #{channel.name} in {guild.name}')
                
                try:
                    welcome_embed = discord.Embed(
                        title="👋 Hello! Market Structure Bot is Online",
                        description="I'm ready to monitor pivot levels and send you alerts!",
                        color=0x00ff88,
                        timestamp=datetime.now()
                    )
                    
                    welcome_embed.add_field(
                        name="📊 Monitoring Stocks", 
                        value=", ".join(STOCKS), 
                        inline=False
                    )
                    
                    welcome_embed.add_field(
                        name="🎯 Alert Threshold", 
                        value=f"${CROSSING_THRESHOLD}", 
                        inline=True
                    )
                    
                    welcome_embed.add_field(
                        name="⏰ Cooldown Period", 
                        value=f"{ALERT_COOLDOWN} seconds", 
                        inline=True
                    )
                    
                    welcome_embed.add_field(
                        name="📈 Features", 
                        value="• Real-time pivot level monitoring\n• Daily pivot calculations\n• Smart alert system", 
                        inline=False
                    )
                    
                    welcome_embed.set_footer(text="Happy trading! 📈")
                    
                    await channel.send(embed=welcome_embed)
                    
                    await asyncio.sleep(5)
                    await channel.send("✅ **Discord connection test successful!** Bot is ready to receive commands.")
                    
                    try:
                        print("🔄 Syncing slash commands...")
                        synced = await tree.sync()
                        print(f"✅ Synced {len(synced)} slash commands")
                    except Exception as e:
                        print(f"❌ Failed to sync slash commands: {e}")
                    
                    return
                    
                except discord.Forbidden:
                    print(f"❌ Permission denied when trying to send message to #{channel.name}")
                except Exception as e:
                    print(f"❌ Error sending welcome message: {e}")
    
    if not discord_channel_obj:
        print(f"❌ Could not find Discord channel '{DISCORD_CHANNEL}' in any server!")
        print("💡 Troubleshooting checklist:")
        print("   1. ✅ Bot is invited to your Discord server")
        print("   2. ❓ A text channel named 'pivots' exists") 
        print("   3. ❓ Bot has 'View Channels' permission")
        print("   4. ❓ Bot has 'Send Messages' permission")
        print("   5. ❓ Bot has 'Embed Links' permission")
        print("")
        print("🔧 To fix this:")
        print("   - Create a text channel called 'pivots' in your server")
        print("   - Or change DISCORD_CHANNEL in your .env file to match an existing channel")
        print("   - Ensure bot has proper permissions in that channel")

@tree.command(name="stocks", description="Show which stocks the bot is monitoring")
async def stocks_command(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="📈 Monitored Stocks",
            description="The bot is currently monitoring these stocks for pivot level crossings:",
            color=0x00ff88,
            timestamp=datetime.now()
        )
        
        stock_list = ", ".join(STOCKS)
        embed.add_field(
            name="🎯 Active Stocks", 
            value=f"**{stock_list}**", 
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Settings", 
            value=f"• **Threshold:** ${CROSSING_THRESHOLD}\n• **Cooldown:** {ALERT_COOLDOWN}s\n• **Timeframe:** {PIVOT_TIMEFRAME}", 
            inline=True
        )
        
        stocks_with_pivots = len([s for s in STOCKS if pivot_levels.get(s)])
        embed.add_field(
            name="📊 Status", 
            value=f"• **Pivot Data:** {stocks_with_pivots}/{len(STOCKS)} stocks loaded\n• **Real-time:** {'✅ Active' if any(pivot_levels.values()) else '⏳ Loading'}", 
            inline=True
        )
        
        if any(pivot_levels.values()):
            pivot_text = ""
            for stock in STOCKS:
                if pivot_levels.get(stock):
                    levels = pivot_levels[stock]
                    pivot_price = levels.get('Pivot', 0)
                    pivot_text += f"**{stock}**: Pivot ${pivot_price:.2f}\n"
                else:
                    pivot_text += f"**{stock}**: Loading...\n"
            
            embed.add_field(
                name="🎯 Current Pivot Points", 
                value=pivot_text, 
                inline=False
            )
        
        embed.set_footer(text="Use !pivots for detailed pivot levels")
        
        await interaction.response.send_message(embed=embed)
        print(f"✅ Slash command /stocks used by {interaction.user} in {interaction.guild.name}")
        
    except Exception as e:
        print(f"❌ Error in /stocks command: {e}")
        await interaction.response.send_message("❌ Error retrieving stock information.", ephemeral=True)

@tree.command(name="status", description="Show bot status and connection info")
async def status_command(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="🤖 Bot Status",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🔗 Connections", 
            value="• **Discord:** ✅ Online\n• **Alpaca API:** ✅ Connected\n• **WebSocket:** ✅ Active" if any(pivot_levels.values()) else "• **Discord:** ✅ Online\n• **Alpaca API:** ⏳ Connecting\n• **WebSocket:** ⏳ Starting", 
            inline=True
        )
        
        embed.add_field(
            name="📊 Monitoring", 
            value=f"• **Stocks:** {len(STOCKS)}\n• **Channel:** #{DISCORD_CHANNEL}\n• **Mode:** Live Trading", 
            inline=True
        )
        
        embed.add_field(
            name="⚡ Performance", 
            value=f"• **Servers:** {len(discord_client.guilds)}\n• **Pivot Updates:** Daily\n• **Alert Cooldown:** {ALERT_COOLDOWN}s", 
            inline=True
        )
        
        embed.set_footer(text="Bot is running smoothly! 🚀")
        
        await interaction.response.send_message(embed=embed)
        print(f"✅ Slash command /status used by {interaction.user} in {interaction.guild.name}")
        
    except Exception as e:
        print(f"❌ Error in /status command: {e}")
        await interaction.response.send_message("❌ Error retrieving bot status.", ephemeral=True)

@tree.command(name="pivots", description="Show detailed pivot levels for all monitored stocks")
async def pivots_command(interaction: discord.Interaction):
    try:
        if not any(pivot_levels.values()):
            embed = discord.Embed(
                title="⏳ Pivot Levels Loading",
                description="No pivot data available yet. Try requesting a specific stock with `/pivots` or wait for data to load.",
                color=0xffaa00,
                timestamp=datetime.now()
            )
            embed.set_footer(text="Use /pivots to see available stocks")
            await interaction.response.send_message(embed=embed)
            return
        
        embed = discord.Embed(
            title="📊 Current Pivot Levels",
            description="Detailed pivot points for all monitored stocks:",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        for stock, levels in pivot_levels.items():
            if levels:
                level_text = ""
                level_order = ['R3', 'R2', 'R1', 'Pivot', 'S1', 'S2', 'S3']
                
                for level_name in level_order:
                    if level_name in levels:
                        level_value = levels[level_name]
                        if level_name == 'Pivot':
                            level_text += f"🎯 **{level_name}**: ${level_value:.2f}\n"
                        elif 'R' in level_name:
                            level_text += f"⬆️ **{level_name}**: ${level_value:.2f}\n"
                        elif 'S' in level_name:
                            level_text += f"⬇️ **{level_name}**: ${level_value:.2f}\n"
                        else:
                            level_text += f"📈 **{level_name}**: ${level_value:.2f}\n"
                
                try:
                    latest_trade = api.get_latest_trade(stock)
                    if latest_trade:
                        current_price = latest_trade.price
                        level_text += f"\n💰 **Current Price**: ${current_price:.2f}"
                        print(f"📊 Added current price: ${current_price:.2f}")
                    else:
                        current_bars = api.get_bars(stock, '1Min', limit=1).df
                        if len(current_bars) > 0:
                            current_price = current_bars['close'].iloc[0]
                            level_text += f"\n💰 **Current Price**: ${current_price:.2f}"
                            print(f"📊 Added current price (from bar): ${current_price:.2f}")
                        else:
                            level_text += f"\n💰 **Current Price**: Unavailable"
                            print(f"⚠️ No current price data available for {stock}")
                except Exception as e:
                    print(f"⚠️ Could not fetch current price for {stock}: {e}")
                    level_text += f"\n💰 **Current Price**: Loading..."
                
                embed.add_field(
                    name=f"📈 {stock}", 
                    value=level_text, 
                    inline=True
                )
                print(f"📈 Added {stock} data to embed")
            else:
                embed.add_field(
                    name=f"⏳ {stock}", 
                    value="Use `/pivots` to fetch data", 
                    inline=True
                )
                print(f"⏳ No data for {stock}")
        
        embed.add_field(
            name="ℹ️ How to Read", 
            value="🎯 **Pivot**: Main support/resistance\n⬆️ **R1/R2**: Resistance levels\n⬇️ **S1/S2**: Support levels", 
            inline=False
        )
        
        embed.set_footer(text="Pivot levels are recalculated daily at market close")
        
        await interaction.response.send_message(embed=embed)
        print(f"✅ Slash command /pivots used by {interaction.user} in {interaction.guild.name}")
        
    except Exception as e:
        print(f"❌ Error in /pivots command: {e}")
        await interaction.response.send_message("❌ Error retrieving pivot levels.", ephemeral=True)

@discord_client.event
async def on_message(message):
    print(f"📨 Message received: '{message.content}' from {message.author} in #{message.channel.name}")
    
    if message.author == discord_client.user:
        print(f"🚫 Ignoring own message from bot user")
        return
    
    print(f"✅ Message is not from bot, proceeding...")
    
    if message.channel.name != DISCORD_CHANNEL:
        print(f"🚫 Message not in target channel. Expected: '{DISCORD_CHANNEL}', Got: '{message.channel.name}'")
        return
    
    print(f"✅ Message is in correct channel '{DISCORD_CHANNEL}', processing commands...")
    
    if message.content.lower() == '!test':
        print(f"🎯 Processing !test command")
        await message.channel.send("🤖 **Bot is working!** All systems operational.")
        print(f"✅ !test command completed")
    
    elif message.content.lower() == '!ping':
        print(f"🎯 Processing !ping command")
        await message.channel.send("🏓 **Pong!** Bot is responsive.")
        print(f"✅ !ping command completed")
    
    elif message.content.lower() == '!status':
        print(f"🎯 Processing !status command")
        status_embed = discord.Embed(
            title="🔍 Bot Status",
            description="Discord connection: ✅ Online",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        status_embed.add_field(name="📊 Monitoring", value=", ".join(STOCKS), inline=False)
        status_embed.add_field(name="🎯 Mode", value="Live Trading Mode", inline=True)
        status_embed.add_field(name="📈 Pivot Levels", value=f"{len([s for s in STOCKS if pivot_levels.get(s)])} stocks loaded", inline=True)
        await message.channel.send(embed=status_embed)
        print(f"✅ !status command completed")
    
    elif message.content.lower() == '!stocks':
        print(f"🎯 Processing !stocks command")
        stocks_embed = discord.Embed(
            title="📈 Monitored Stocks",
            description="The bot is currently monitoring these stocks for pivot level crossings:",
            color=0x00ff88,
            timestamp=datetime.now()
        )
        
        # Add basic stock info
        stock_list = ", ".join(STOCKS)
        stocks_embed.add_field(
            name="🎯 Active Stocks", 
            value=f"**{stock_list}**", 
            inline=False
        )
        
        stocks_embed.add_field(
            name="⚙️ Settings", 
            value=f"• **Threshold:** ${CROSSING_THRESHOLD}\n• **Cooldown:** {ALERT_COOLDOWN}s\n• **Timeframe:** {PIVOT_TIMEFRAME}", 
            inline=True
        )
        
        stocks_with_pivots = len([s for s in STOCKS if pivot_levels.get(s)])
        stocks_embed.add_field(
            name="📊 Status", 
            value=f"• **Pivot Data:** {stocks_with_pivots}/{len(STOCKS)} stocks loaded\n• **Real-time:** {'✅ Active' if any(pivot_levels.values()) else '⏳ Loading'}", 
            inline=True
        )
        
        status_text = ""
        for stock in STOCKS:
            if pivot_levels.get(stock):
                status_text += f"✅ **{stock}** - Data loaded\n"
            else:
                status_text += f"⏳ **{stock}** - Use `!pivots {stock}` to load\n"
        
        stocks_embed.add_field(
            name="📋 Stock Status", 
            value=status_text, 
            inline=False
        )
        
        stocks_embed.set_footer(text="Use !pivots TICKER to view specific stock pivots")
        
        await message.channel.send(embed=stocks_embed)
        print(f"✅ !stocks command completed")
    
    elif message.content.lower().startswith('!pivots'):
        print(f"🎯 Processing !pivots command")
        parts = message.content.split()
        print(f"📝 Command parts: {parts} (length: {len(parts)})")
        
        if len(parts) != 2:
            print(f"❌ Wrong number of arguments in !pivots command: {len(parts)} parts")
            await message.channel.send("❌ **Usage**: `!pivots TICKER`\nExample: `!pivots AAPL`\n\nAvailable stocks: " + ", ".join(STOCKS))
            print(f"✅ Usage error message sent")
            return
        
        ticker = parts[1].upper()
        print(f"📈 Specific ticker requested: {ticker}")
        
        if not pivot_levels.get(ticker):
            print(f"⏳ No pivot data for {ticker}, fetching on-demand")
            loading_msg = await message.channel.send(f"⏳ Fetching pivot data for **{ticker}**...")
            print(f"📤 Loading message sent")
            
            pivot_data = await fetch_pivot_data_for_stock(ticker)
            print(f"📊 Fetch result for {ticker}: {'Success' if pivot_data else 'Failed'}")
            
            if not pivot_data:
                print(f"❌ Failed to fetch pivot data for {ticker}")
                await loading_msg.edit(content=f"❌ Failed to fetch pivot data for **{ticker}**. Please try again later.")
                print(f"✅ Error message updated")
                return
            
            await loading_msg.delete()
            print(f"🗑️ Loading message deleted")
        else:
            print(f"✅ Found cached pivot data for {ticker}")
        
        levels = pivot_levels[ticker]
        print(f"📊 Creating embed for {ticker} with levels: {list(levels.keys())}")
        
        embed = discord.Embed(
            title=f"📊 {ticker} Pivot Analysis",
            description=f"Detailed pivot points for **{ticker}**:",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        level_text = ""
        
        level_order = ['R3', 'R2', 'R1', 'Pivot', 'S1', 'S2', 'S3']
        
        for level_name in level_order:
            if level_name in levels:
                level_value = levels[level_name]
                if level_name == 'Pivot':
                    level_text += f"🎯 **{level_name}**: ${level_value:.2f}\n"
                elif 'R' in level_name:  # Resistance levels
                    level_text += f"⬆️ **{level_name}**: ${level_value:.2f}\n"
                elif 'S' in level_name:  # Support levels
                    level_text += f"⬇️ **{level_name}**: ${level_value:.2f}\n"
                else:
                    level_text += f"📈 **{level_name}**: ${level_value:.2f}\n"
                print(f"📝 Added {level_name}: ${level_value:.2f}")
        
        # Add current price if available
        try:
            # Get the latest trade for current price
            latest_trade = api.get_latest_trade(ticker)
            if latest_trade:
                current_price = latest_trade.price
                level_text += f"\n💰 **Current Price**: ${current_price:.2f}"
                print(f"📊 Added current price: ${current_price:.2f}")
            else:
                # Fallback to latest bar if no trade available
                current_bars = api.get_bars(ticker, '1Min', limit=1).df
                if len(current_bars) > 0:
                    current_price = current_bars['close'].iloc[0]
                    level_text += f"\n💰 **Current Price**: ${current_price:.2f}"
                    print(f"📊 Added current price (from bar): ${current_price:.2f}")
                else:
                    level_text += f"\n💰 **Current Price**: Unavailable"
                    print(f"⚠️ No current price data available for {ticker}")
        except Exception as e:
            print(f"⚠️ Could not fetch current price for {ticker}: {e}")
            level_text += f"\n💰 **Current Price**: Loading..."
        
        embed.add_field(
            name="📈 Pivot Levels", 
            value=level_text, 
            inline=False
        )
        
        embed.set_footer(text=f"Pivot levels for {ticker} • Updated daily at market close")
        await message.channel.send(embed=embed)
        print(f"✅ !pivots {ticker} command completed")
    
    else:
        print(f"❓ Unknown command: '{message.content}' - no matching command found")
    
    print(f"📨 Message processing completed for: '{message.content}'")

async def send_discord_alert(symbol, pivot_level, price, timestamp):
    print(f"📤 Attempting to send Discord alert for {symbol} {pivot_level} at ${price:.2f}")
    
    if not discord_channel_obj:
        print(f"❌ No Discord channel available for alert")
        return
    
    try:
        print(f"📝 Creating Discord embed for {symbol} alert")
        embed = discord.Embed(
            title="📊 Pivot Level Alert",
            color=0x00ff00 if 'R' in pivot_level else 0xff0000,
            timestamp=datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        )
        
        embed.add_field(name="Symbol", value=f"**{symbol}**", inline=True)
        embed.add_field(name="Pivot Level", value=f"**{pivot_level}**", inline=True)
        embed.add_field(name="Price", value=f"**${price:.2f}**", inline=True)
        
        if pivot_level == 'Pivot':
            embed.description = "🎯 Price is near the main pivot point"
        elif 'R' in pivot_level:
            embed.description = f"⬆️ Price is approaching resistance level {pivot_level}"
        elif 'S' in pivot_level:
            embed.description = f"⬇️ Price is approaching support level {pivot_level}"
        
        print(f"📤 Sending alert to Discord channel: #{discord_channel_obj.name}")
        await discord_channel_obj.send(embed=embed)
        print(f"✅ Discord alert sent successfully for {symbol} {pivot_level}")
        
    except Exception as e:
        print(f"❌ Error sending Discord alert for {symbol}: {e}")
        import traceback
        print(f"📋 Full traceback:\n{traceback.format_exc()}")

def calculate_pivot_points(high, low, close):
    """
    Calculate traditional pivot points based on previous day's High, Low, Close.
    
    Traditional Pivot Point Rules:
    - Pivot = (High + Low + Close) / 3
    - R1 = Pivot + (Pivot - Low) = Above pivot at distance equal to pivot-to-low
    - S1 = Pivot - (High - Pivot) = Below pivot at distance equal to high-to-pivot  
    - R2 = Pivot + (High - Low) = Above pivot at distance equal to trading range
    - S2 = Pivot - (High - Low) = Below pivot at distance equal to trading range
    - R3 = R2 + (High - Low) = Above second resistance at distance equal to trading range
    - S3 = S2 - (High - Low) = Below second support at distance equal to trading range
    """
    print(f"🧮 Starting pivot calculation with inputs:")
    print(f"   High: ${high:.2f}")
    print(f"   Low: ${low:.2f}")
    print(f"   Close: ${close:.2f}")
    
    # Calculate pivot point
    pivot = (high + low + close) / 3
    print(f"🧮 Pivot = (${high:.2f} + ${low:.2f} + ${close:.2f}) / 3 = ${pivot:.2f}")
    
    # Calculate trading range
    trading_range = high - low
    print(f"🧮 Trading Range = ${high:.2f} - ${low:.2f} = ${trading_range:.2f}")
    
    # First level resistance and support
    r1 = pivot + (pivot - low)  # Above pivot at distance equal to pivot-to-low
    s1 = pivot - (high - pivot)  # Below pivot at distance equal to high-to-pivot
    
    print(f"🧮 R1 = ${pivot:.2f} + (${pivot:.2f} - ${low:.2f}) = ${pivot:.2f} + ${(pivot - low):.2f} = ${r1:.2f}")
    print(f"🧮 S1 = ${pivot:.2f} - (${high:.2f} - ${pivot:.2f}) = ${pivot:.2f} - ${(high - pivot):.2f} = ${s1:.2f}")
    
    # Second level resistance and support  
    r2 = pivot + trading_range  # Above pivot at distance equal to trading range
    s2 = pivot - trading_range  # Below pivot at distance equal to trading range
    
    print(f"🧮 R2 = ${pivot:.2f} + ${trading_range:.2f} = ${r2:.2f}")
    print(f"🧮 S2 = ${pivot:.2f} - ${trading_range:.2f} = ${s2:.2f}")
    
    # Third level resistance and support
    r3 = r2 + trading_range  # Above second resistance at distance equal to trading range
    s3 = s2 - trading_range  # Below second support at distance equal to trading range
    
    print(f"🧮 R3 = ${r2:.2f} + ${trading_range:.2f} = ${r3:.2f}")
    print(f"🧮 S3 = ${s2:.2f} - ${trading_range:.2f} = ${s3:.2f}")
    
    result = {'Pivot': pivot, 'R1': r1, 'S1': s1, 'R2': r2, 'S2': s2, 'R3': r3, 'S3': s3}
    print(f"🎯 Final pivot levels: {result}")
    
    return result

async def fetch_pivot_data_for_stock(stock):
    try:
        print(f"📊 Fetching pivot data for {stock}...")
        
        # Get the last trading day (skip weekends)
        from datetime import datetime, timedelta
        def get_last_trading_day():
            today = datetime.utcnow().date()
            offset = 1
            while True:
                candidate = today - timedelta(days=offset)
                if candidate.weekday() < 5:  # Mon-Fri are 0-4
                    return candidate
                offset += 1
        
        last_trading_day = get_last_trading_day()
        print(f"📅 Fetching data for {stock} on {last_trading_day}...")
        
        # Use the working market data API approach
        headers = {
            'APCA-API-KEY-ID': API_KEY,
            'APCA-API-SECRET-KEY': API_SECRET
        }
        
        params = {
            'timeframe': '1Day',
            'start': last_trading_day.strftime('%Y-%m-%d'),
            'end': last_trading_day.strftime('%Y-%m-%d'),
            'limit': 1
        }
        
        url = f"{DATA_URL}/stocks/{stock}/bars"
        
        response = requests.get(url, headers=headers, params=params)
        print(f"📡 API response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ API error: {response.status_code} {response.text}")
            return None
        
        data = response.json()
        bars = data.get('bars', [])
        
        if not bars:
            print(f"❌ No data returned for {stock} on {last_trading_day}")
            return None
        
        bar = bars[0]
        high = bar['h']
        low = bar['l']
        close = bar['c']
        
        print(f"📈 Data extracted for {stock} (last trading day - {last_trading_day}):")
        print(f"   High: ${high:.2f}")
        print(f"   Low: ${low:.2f}")
        print(f"   Close: ${close:.2f}")
        
        pivot_data = calculate_pivot_points(high, low, close)
        pivot_levels[stock] = pivot_data
        
        print(f"✅ Updated pivot levels for {stock}: {pivot_data}")
        print(f"📊 Total stocks with pivot data: {len([s for s in STOCKS if pivot_levels.get(s)])}/{len(STOCKS)}")
        return pivot_data
        
    except Exception as e:
        print(f"❌ Error fetching pivot data for {stock}: {e}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        print(f"❌ Full traceback:\n{traceback.format_exc()}")
        return None

def update_pivot_levels():
    for stock in STOCKS:
        try:
            print(f"🔄 Updating pivot levels for {stock}...")
            
            # Get the last trading day (skip weekends)
            from datetime import datetime, timedelta
            def get_last_trading_day():
                today = datetime.utcnow().date()
                offset = 1
                while True:
                    candidate = today - timedelta(days=offset)
                    if candidate.weekday() < 5:  # Mon-Fri are 0-4
                        return candidate
                    offset += 1
            
            last_trading_day = get_last_trading_day()
            print(f"📅 Fetching data for {stock} on {last_trading_day}...")
            
            # Use the working market data API approach
            headers = {
                'APCA-API-KEY-ID': API_KEY,
                'APCA-API-SECRET-KEY': API_SECRET
            }
            
            params = {
                'timeframe': '1Day',
                'start': last_trading_day.strftime('%Y-%m-%d'),
                'end': last_trading_day.strftime('%Y-%m-%d'),
                'limit': 1
            }
            
            url = f"{DATA_URL}/stocks/{stock}/bars"
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code != 200:
                print(f"❌ API error for {stock}: {response.status_code}")
                continue
            
            data = response.json()
            bars = data.get('bars', [])
            
            if not bars:
                print(f"❌ No data returned for {stock} on {last_trading_day}")
                continue
            
            bar = bars[0]
            high = bar['h']
            low = bar['l']
            close = bar['c']
            
            print(f"📈 Using data for {stock} from {last_trading_day}:")
            print(f"   High: ${high:.2f}")
            print(f"   Low: ${low:.2f}")
            print(f"   Close: ${close:.2f}")
            
            pivot_levels[stock] = calculate_pivot_points(high, low, close)
            print(f"✅ Updated pivot levels for {stock} (last trading day): {pivot_levels[stock]}")
        except Exception as e:
            print(f"❌ Error updating pivot levels for {stock}: {e}")
    
    if discord_channel_obj:
        asyncio.create_task(send_daily_pivots_update())
    
    threading.Timer(86400, update_pivot_levels).start()

async def send_daily_pivots_update():
    if not discord_channel_obj:
        return
    
    try:
        embed = discord.Embed(
            title="📈 Daily Pivot Levels Update",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        for stock, levels in pivot_levels.items():
            if levels:
                level_text = "\n".join([f"{k}: ${v:.2f}" for k, v in levels.items()])
                embed.add_field(name=f"**{stock}**", value=level_text, inline=True)
        
        embed.set_footer(text="Pivot levels recalculated based on previous day's data")
        await discord_channel_obj.send(embed=embed)
        
    except Exception as e:
        print(f"Error sending daily pivot update: {e}")

def on_websocket_message(ws, message):
    try:
        if REAL_TIME_DEBUG:
            print(f"📨 WebSocket message received: {message[:200]}...")
        data = json.loads(message)
        
        if isinstance(data, list):
            if REAL_TIME_DEBUG:
                print(f"📋 Processing {len(data)} messages from WebSocket")
            for i, msg in enumerate(data):
                if REAL_TIME_DEBUG:
                    print(f"📨 Processing message {i+1}/{len(data)}")
                process_websocket_message(msg)
        else:
            if REAL_TIME_DEBUG:
                print(f"📨 Processing single WebSocket message")
            process_websocket_message(data)
            
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse WebSocket message: {e}")
        print(f"📨 Raw message: {message[:200]}...")
    except Exception as e:
        print(f"❌ Error processing WebSocket message: {e}")
        import traceback
        print(f"📋 Full traceback:\n{traceback.format_exc()}")

def process_websocket_message(msg):
    try:
        msg_type = msg.get('T')
        stock = msg.get('S')
        
        if REAL_TIME_DEBUG:
            print(f"🔍 Processing message: Type={msg_type}, Stock={stock}")
        
        if not stock or stock not in STOCKS:
            if REAL_TIME_DEBUG:
                print(f"⏭️ Skipping {stock} - not in monitored stocks: {STOCKS}")
            return
            
        price = 0
        
        if msg_type == 'q':  # Quote
            ask_price = msg.get('ap', 0)
            bid_price = msg.get('bp', 0)
            if REAL_TIME_DEBUG:
                print(f"💬 Quote for {stock}: Ask=${ask_price}, Bid=${bid_price}")
            if ask_price > 0 and bid_price > 0:
                price = (ask_price + bid_price) / 2
                if REAL_TIME_DEBUG:
                    print(f"💰 Calculated quote price for {stock}: ${price:.2f}")
            else:
                if REAL_TIME_DEBUG:
                    print(f"⚠️ Invalid quote prices for {stock}: Ask=${ask_price}, Bid=${bid_price}")
        elif msg_type == 't':  # Trade
            price = msg.get('p', 0)
            if REAL_TIME_DEBUG:
                print(f"💱 Trade for {stock}: ${price:.2f}")
        else:
            if REAL_TIME_DEBUG:
                print(f"❓ Unknown message type: {msg_type}")
            return
        
        if price > 0:
            if REAL_TIME_DEBUG:
                print(f"🎯 Calling check_pivot_crossing for {stock} at ${price:.2f}")
            check_pivot_crossing(stock, price)
        else:
            if REAL_TIME_DEBUG:
                print(f"⚠️ Invalid price for {stock}: ${price}")
            
    except Exception as e:
        print(f"❌ Error processing individual message: {e}")
        import traceback
        print(f"📋 Full traceback:\n{traceback.format_exc()}")

def check_pivot_crossing(stock, price):
    if REAL_TIME_DEBUG:
        print(f"🔍 Checking pivot crossing for {stock} at ${price:.2f}")
    
    if stock not in pivot_levels or not pivot_levels[stock]:
        if REAL_TIME_DEBUG:
            print(f"⏳ No pivot data available for {stock}, fetching on-demand...")
            print(f"📊 Available pivot data: {list(pivot_levels.keys())}")
        
        # Fetch pivot data lazily
        try:
            if REAL_TIME_DEBUG:
                print(f"📈 Fetching pivot data for {stock}...")
            pivot_data = asyncio.run(fetch_pivot_data_for_stock(stock))
            if pivot_data:
                if REAL_TIME_DEBUG:
                    print(f"✅ Successfully loaded pivot data for {stock}: {pivot_data}")
                # Now check the crossing again with the loaded data
                check_pivot_crossing(stock, price)
            else:
                if REAL_TIME_DEBUG:
                    print(f"❌ Failed to load pivot data for {stock}")
        except Exception as e:
            if REAL_TIME_DEBUG:
                print(f"❌ Error fetching pivot data for {stock}: {e}")
        return
    
    if REAL_TIME_DEBUG:
        print(f"📊 Pivot levels for {stock}: {pivot_levels[stock]}")
    
    current_time = datetime.utcnow().isoformat() + 'Z'
    
    # Find the closest pivot level that the price is approaching
    closest_level = None
    closest_distance = float('inf')
    approaching_direction = None
    
    for level_name, level_value in pivot_levels[stock].items():
        distance = abs(price - level_value)
        
        if REAL_TIME_DEBUG:
            print(f"📏 {stock} ${price:.2f} vs {level_name} ${level_value:.2f} = distance ${distance:.2f} (threshold: ${CROSSING_THRESHOLD})")
        
        # Only consider levels within threshold
        if distance < CROSSING_THRESHOLD:
            # Determine if price is approaching from above or below
            if price > level_value:
                direction = "down"  # Price is above level, approaching from above
            else:
                direction = "up"    # Price is below level, approaching from below
            
            if REAL_TIME_DEBUG:
                print(f"🎯 {stock} at ${price:.2f} is approaching {level_name} ${level_value:.2f} from {direction}")
            
            # Keep track of the closest level within threshold
            if distance < closest_distance:
                closest_distance = distance
                closest_level = level_name
                approaching_direction = direction
    
    # If we found a level to alert on
    if closest_level:
        level_value = pivot_levels[stock][closest_level]
        
        # Create a unique key for this specific crossing to prevent duplicates
        # Round price to 1 decimal place to prevent spam from tiny price fluctuations
        crossing_key = f"{stock}_{closest_level}_{price:.1f}"
        
        # Check if we've already processed this exact crossing recently
        current_time_seconds = time.time()
        if crossing_key in last_alert and current_time_seconds - last_alert[crossing_key] < ALERT_COOLDOWN:
            if REAL_TIME_DEBUG:
                print(f"⏳ Duplicate crossing detected for {crossing_key}, skipping alert")
            return
        
        print(f"🎯 PIVOT CROSSING DETECTED! {stock} at ${price:.2f} approaching {closest_level} ${level_value:.2f} from {approaching_direction}")
        
        print(f"📤 Sending Discord alert for {stock} {closest_level} at ${price:.2f}")
        
        if discord_client.is_ready():
            # Schedule the alert in the main event loop
            loop = discord_client.loop
            if loop and loop.is_running():
                loop.call_soon_threadsafe(
                    lambda level=closest_level, p=price, t=current_time: asyncio.create_task(send_discord_alert(stock, level, p, t))
                )
                # Mark this crossing as processed
                last_alert[crossing_key] = current_time_seconds
                print(f"✅ Alert scheduled and cooldown set for {crossing_key}")
            else:
                print(f"❌ Discord event loop not available, cannot send alert")
        else:
            print(f"❌ Discord client not ready, cannot send alert")
    else:
        if REAL_TIME_DEBUG:
            print(f"➡️ No pivot level crossings detected for {stock} at ${price:.2f}")

websocket_reconnect_count = 0
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 30

def on_error(ws, error):
    print(f"WebSocket error: {error}")
    global websocket_reconnect_count
    websocket_reconnect_count += 1

def on_close(ws, close_status_code, close_msg):
    global websocket_reconnect_count
    if REAL_TIME_DEBUG:
        print(f"WebSocket closed (code: {close_status_code}, msg: {close_msg})")
    
    if websocket_reconnect_count < MAX_RECONNECT_ATTEMPTS:
        if REAL_TIME_DEBUG:
            print(f"🔄 Reconnecting... (attempt {websocket_reconnect_count + 1}/{MAX_RECONNECT_ATTEMPTS})")
        time.sleep(RECONNECT_DELAY)
        start_websocket()
    else:
        print(f"❌ Max reconnection attempts reached ({MAX_RECONNECT_ATTEMPTS}). Stopping WebSocket reconnection.")
        print("💡 You can restart the bot to re-enable real-time alerts.")

def on_open(ws):
    global websocket_reconnect_count
    websocket_reconnect_count = 0
    if REAL_TIME_DEBUG:
        print("✅ WebSocket opened successfully")
    
    try:
        auth_message = {"action": "auth", "key": API_KEY, "secret": API_SECRET}
        ws.send(json.dumps(auth_message))
        if REAL_TIME_DEBUG:
            print("🔐 WebSocket authentication sent")
        
        for stock in STOCKS:
            subscribe_message = {"action": "subscribe", "quotes": [stock]}
            ws.send(json.dumps(subscribe_message))
        if REAL_TIME_DEBUG:
            print(f"📡 Subscribed to quotes for {len(STOCKS)} stocks")
        
    except Exception as e:
        print(f"❌ Error during WebSocket setup: {e}")

def start_websocket():
    """Start WebSocket for real-time quotes"""
    try:
        ws_url = "wss://stream.data.alpaca.markets/v2/iex"  # IEX for paper trading
        ws = websocket.WebSocketApp(ws_url,
                                    on_message=on_websocket_message,
                                    on_error=on_error,
                                    on_close=on_close,
                                    on_open=on_open)
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        if REAL_TIME_DEBUG:
            print("✅ WebSocket connection started for real-time data")
    except Exception as e:
        print(f"❌ Error starting WebSocket: {e}")

async def run_discord_bot():
    """Run the Discord bot"""
    await discord_client.start(DISCORD_TOKEN)

def run_trading_bot():
    """Run the trading bot logic"""
    print("🤖 Starting trading bot...")
    
    # Don't initialize pivot levels at startup - load them on-demand
    print("📊 Pivot levels will be loaded on-demand when requested")
    
    # Start WebSocket for real-time data
    if REAL_TIME_DEBUG:
        print("🔗 Starting real-time data connection...")
    start_websocket()
    
    # Start polling as backup if WebSocket fails
    if REAL_TIME_DEBUG:
        print("🔄 Starting polling backup system...")
    polling_thread = threading.Thread(target=run_polling_backup, daemon=True)
    polling_thread.start()
    
    # Keep script running
    print("✅ Trading bot is now monitoring pivot levels!")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("🛑 Shutting down trading bot...")

def run_polling_backup():
    """Poll for price updates as backup to WebSocket"""
    if REAL_TIME_DEBUG:
        print("📡 Polling backup system started")
    poll_count = 0
    while True:
        try:
            time.sleep(60)  # Poll every minute
            poll_count += 1
            if REAL_TIME_DEBUG:
                print(f"📡 Polling backup cycle #{poll_count}")
            
            # Only poll if we have pivot data loaded
            if not any(pivot_levels.values()):
                if REAL_TIME_DEBUG:
                    print(f"⏭️ Skipping poll cycle #{poll_count} - no pivot data loaded")
                    print(f"📊 Available pivot data: {list(pivot_levels.keys())}")
                continue
                
            stocks_with_pivots = [s for s in STOCKS if pivot_levels.get(s)]
            if REAL_TIME_DEBUG:
                print(f"📊 Polling {len(stocks_with_pivots)} stocks with pivot data: {stocks_with_pivots}")
                
            for stock in stocks_with_pivots:
                try:
                    if REAL_TIME_DEBUG:
                        print(f"📡 Polling {stock}...")
                    # Get latest trade
                    trades = api.get_trades(stock, limit=1)
                    if trades and len(trades) > 0:
                        latest_trade = trades[0]
                        price = latest_trade.price
                        if REAL_TIME_DEBUG:
                            print(f"💰 Polled {stock} price: ${price:.2f}")
                        if price > 0:
                            check_pivot_crossing(stock, price)
                        else:
                            if REAL_TIME_DEBUG:
                                print(f"⚠️ Invalid price for {stock}: ${price}")
                    else:
                        if REAL_TIME_DEBUG:
                            print(f"❌ No trades found for {stock}")
                except Exception as e:
                    if REAL_TIME_DEBUG:
                        print(f"❌ Error polling {stock}: {e}")
                    
        except Exception as e:
            print(f"❌ Error in polling backup: {e}")
            import traceback
            print(f"📋 Full traceback:\n{traceback.format_exc()}")
            time.sleep(60)

async def test_alpaca_connection():
    try:
        account = api.get_account()
        print(f"✅ Alpaca connection successful")
        print(f"📊 Account status: {account.status}")
        print(f"💰 Buying power: ${account.buying_power}")
        
        print(f"🔍 Testing data availability for TSLA...")
        try:
            bars_1day = api.get_bars('TSLA', '1Day', limit=5).df
            print(f"📊 1Day bars for TSLA: {len(bars_1day)} rows")
            if len(bars_1day) > 0:
                print(f"📈 Latest TSLA data: {bars_1day.iloc[-1]}")
        except Exception as e:
            print(f"❌ Error fetching 1Day TSLA data: {e}")
            
        try:
            bars_1min = api.get_bars('TSLA', '1Min', limit=10).df
            print(f"📊 1Min bars for TSLA: {len(bars_1min)} rows")
            if len(bars_1min) > 0:
                print(f"📈 Latest TSLA 1min data: {bars_1min.iloc[-1]}")
        except Exception as e:
            print(f"❌ Error fetching 1Min TSLA data: {e}")
            
        return True
    except Exception as e:
        print(f"❌ Alpaca connection failed: {e}")
        return False

async def main():
    """Main function to run both Discord bot and trading functionality"""
    print("🚀 Starting Market Structure Bot...")
    print(f"📊 Monitoring stocks: {STOCKS}")
    print(f"🎯 Pivot timeframe: {PIVOT_TIMEFRAME}")
    print(f"💰 Alert threshold: ${CROSSING_THRESHOLD}")
    print(f"⏰ Alert cooldown: {ALERT_COOLDOWN} seconds")
    
    try:
        await test_alpaca_connection()
    except Exception as e:
        print(f"❌ Failed to test Alpaca connection: {e}")
    
    # Create tasks for Discord bot
    discord_task = asyncio.create_task(run_discord_bot())
    
    # Run trading bot in a separate thread
    trading_thread = threading.Thread(target=run_trading_bot)
    trading_thread.daemon = True
    trading_thread.start()
    
    try:
        # Wait for Discord bot to finish (which should be never)
        await discord_task
    except KeyboardInterrupt:
        print("🛑 Shutting down...")
        await discord_client.close()

if __name__ == "__main__":
    asyncio.run(main())