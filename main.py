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
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL = os.getenv('DISCORD_CHANNEL', 'pivots')
STOCKS = os.getenv('STOCKS', 'AAPL,MSFT,TSLA').split(',')
PIVOT_TIMEFRAME = os.getenv('PIVOT_TIMEFRAME', '1Day')
CROSSING_THRESHOLD = float(os.getenv('CROSSING_THRESHOLD', '0.01'))
ALERT_COOLDOWN = int(os.getenv('ALERT_COOLDOWN', '300'))

if not API_KEY or not API_SECRET:
    raise ValueError("ALPACA_API_KEY and ALPACA_API_SECRET environment variables are required")
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable is required")

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

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
    if not discord_channel_obj:
        print("⚠️  Discord channel not available")
        return
    
    try:
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
        
        await discord_channel_obj.send(embed=embed)
        print(f"✅ Discord alert sent for {symbol}: {pivot_level} at ${price:.2f}")
        
    except Exception as e:
        print(f"❌ Error sending Discord alert for {symbol}: {e}")

def calculate_pivot_points(high, low, close):
    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)
    return {'Pivot': pivot, 'R1': r1, 'S1': s1, 'R2': r2, 'S2': s2, 'R3': r3, 'S3': s3}

async def fetch_pivot_data_for_stock(stock):
    try:
        print(f"📊 Fetching pivot data for {stock}...")
        print(f"🔧 Using timeframe: {PIVOT_TIMEFRAME}")
        print(f"🔧 Using base URL: {BASE_URL}")
        
        print(f"📡 Making API call to Alpaca for {stock} (requesting 10 days)...")
        bars_response = api.get_bars(stock, PIVOT_TIMEFRAME, limit=10)
        print(f"📡 API response received: {type(bars_response)}")
        
        if bars_response is None:
            print(f"❌ API returned None for {stock}")
            return None
            
        print(f"📊 Converting to DataFrame...")
        bars_df = bars_response.df
        print(f"📊 DataFrame shape: {bars_df.shape}")
        print(f"📊 DataFrame columns: {list(bars_df.columns)}")
        print(f"📊 DataFrame head:\n{bars_df.head()}")
        
        if len(bars_df) < 2:
            print(f"❌ Insufficient data for {stock}. Got {len(bars_df)} rows, need at least 2")
            print(f"📊 Available data:\n{bars_df}")
            
            if len(bars_df) == 1:
                print(f"⚠️ Only 1 day of data available, using current day as pivot reference")
                current_high = bars_df['high'].iloc[0]
                current_low = bars_df['low'].iloc[0]
                current_close = bars_df['close'].iloc[0]
                
                print(f"📈 Using current day data for {stock}:")
                print(f"   High: ${current_high:.2f}")
                print(f"   Low: ${current_low:.2f}")
                print(f"   Close: ${current_close:.2f}")
                
                pivot_data = calculate_pivot_points(current_high, current_low, current_close)
                pivot_levels[stock] = pivot_data
                
                print(f"⚠️ Calculated pivot levels using current day data: {pivot_data}")
                return pivot_data
            
            return None
            
        print(f"✅ Got sufficient data for {stock}")
        
        prev_high = bars_df['high'].iloc[-2]
        prev_low = bars_df['low'].iloc[-2]
        prev_close = bars_df['close'].iloc[-2]
        
        print(f"📈 Data extracted for {stock} (previous trading day):")
        print(f"   High: ${prev_high:.2f}")
        print(f"   Low: ${prev_low:.2f}")
        print(f"   Close: ${prev_close:.2f}")
        
        pivot_data = calculate_pivot_points(prev_high, prev_low, prev_close)
        pivot_levels[stock] = pivot_data
        
        print(f"✅ Updated pivot levels for {stock}: {pivot_data}")
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
            bars = api.get_bars(stock, PIVOT_TIMEFRAME, limit=2).df
            if len(bars) < 2:
                print(f"Insufficient data for {stock}")
                continue
            prev_high = bars['high'][-2]
            prev_low = bars['low'][-2]
            prev_close = bars['close'][-2]
            pivot_levels[stock] = calculate_pivot_points(prev_high, prev_low, prev_close)
            print(f"Updated pivot levels for {stock}: {pivot_levels[stock]}")
        except Exception as e:
            print(f"Error updating pivot levels for {stock}: {e}")
    
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
        data = json.loads(message)
        for msg in data:
            if msg.get('T') == 'q':
                stock = msg['S']
                if stock in STOCKS:
                    price = (msg.get('ap', 0) + msg.get('bp', 0)) / 2
                    if price > 0:
                        check_pivot_crossing(stock, price)
            elif msg.get('T') == 't':
                stock = msg['S']
                if stock in STOCKS:
                    price = msg.get('p', 0)
                    if price > 0:
                        check_pivot_crossing(stock, price)
    except Exception as e:
        print(f"Error processing WebSocket message: {e}")

def check_pivot_crossing(stock, price):
    if stock not in pivot_levels or not pivot_levels[stock]:
        return
    
    current_time = datetime.utcnow().isoformat() + 'Z'
    for level_name, level_value in pivot_levels[stock].items():
        if abs(price - level_value) < CROSSING_THRESHOLD:
            last_alert_time = last_alert[stock].get(level_name, 0)
            if time.time() - last_alert_time < ALERT_COOLDOWN:
                continue
            
            if discord_client.is_ready():
                asyncio.create_task(send_discord_alert(stock, level_name, price, current_time))
                last_alert[stock][level_name] = time.time()

def on_error(ws, error):
    print(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed. Reconnecting...")
    start_websocket()

def on_open(ws):
    print("WebSocket opened")
    ws.send(json.dumps({"action": "auth", "key": API_KEY, "secret": API_SECRET}))
    for stock in STOCKS:
        ws.send(json.dumps({"action": "subscribe", "quotes": [stock]}))

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
    print("🔗 Starting real-time data connection...")
    start_websocket()
    
    # Keep script running
    print("✅ Trading bot is now monitoring pivot levels!")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("🛑 Shutting down trading bot...")

async def main():
    """Main function to run both Discord bot and trading functionality"""
    print("🚀 Starting Market Structure Bot...")
    
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