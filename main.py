import discord
import random
import os
from discord.ext.commands import cooldown, BucketType
from discord.ext import commands
from discord import Game, app_commands
from typing import List
import requests # For the joke API
import time
from datetime import datetime
import asyncio
import json
import socket
import threading
import aiohttp
import logging
import sys

# --- NEW: Load the specific server configuration ---
try:
    import config
except ImportError:
    print("="*50)
    print("ERROR: config.py not found.")
    print("Please copy config.py.example to config.py and fill in the values.")
    print("="*50)
    sys.exit(1)
# ------------------------------------------------

# Environment variables for tokens and keys (from .env file)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")

# Global flag to signal that a voice operation is in progress
voice_operation_in_progress = False

# Dictionary of active Steam monitor tasks {discord_user_id: asyncio.Task}
active_steam_monitors = {}
STEAM_API_POLL_INTERVAL = 300 # Seconds (5 minutes)
STEAM_API_COOLDOWN_BETWEEN_CALLS = 60 # Seconds (1 minute)

# Path to sound files
SOUNDS_DIR = "sounds"
if not os.path.exists(SOUNDS_DIR):
    os.makedirs(SOUNDS_DIR)
    print(f"Directory '{SOUNDS_DIR}' was created. Please place your sound files here.")

WELCOME_SOUND = os.path.join(SOUNDS_DIR, "welcome.wav")
SOUNDS_LIST = [] # Will be populated in on_ready()

# === NOTE: All GIF lists and STEAM_IDS are now loaded from config.py ===


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

activity = discord.Game(name="UwU")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.voice_states = True

# Custom key function for app_commands.checks.cooldown
# This makes the cooldown apply per-user
def interaction_user_key(interaction: discord.Interaction) -> int:
    return interaction.user.id

bot = commands.Bot(command_prefix=None, intents=intents)

# Cooldown for voice events
COOLDOWN_AMOUNT = 10.0  # seconds
last_executed_voice_event = time.time()
def assert_voice_event_cooldown():
    global last_executed_voice_event
    if last_executed_voice_event + COOLDOWN_AMOUNT < time.time():
        last_executed_voice_event = time.time()
        return True
    return False

# Steam API Class
class SteamAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.session = None
        self.last_api_call_time = 0

    async def initialize_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            print("Aiohttp ClientSession initialized for SteamAPI.")

    async def get_player_summary(self, steam_id):
        # Wait for the global cooldown between calls
        time_since_last_call = time.time() - self.last_api_call_time
        if time_since_last_call < STEAM_API_COOLDOWN_BETWEEN_CALLS:
            wait_time = STEAM_API_COOLDOWN_BETWEEN_CALLS - time_since_last_call
            print(f"Waiting {wait_time:.2f}s due to global Steam API cooldown.")
            await asyncio.sleep(wait_time)
        
        self.last_api_call_time = time.time()

        if not self.session or self.session.closed:
            await self.initialize_session()

        url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={self.api_key}&steamids={steam_id}"
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            print(f"Error during Steam API request (HTTP {e.status}): {e.message}")
            return None
        except Exception as e:
            print(f"Unexpected error during Steam API request: {e}")
            return None

    async def monitor_single_steam_user(self, member_id: int, channel_chat_id: int):
        member = bot.get_user(member_id)
        if member is None:
            print(f"Monitor for unknown user {member_id} stopped.")
            return

        # Load Steam ID from config.py
        steam_id = config.STEAM_IDS.get(member.id)
        if not steam_id:
            print(f"No Steam ID found for Discord user {member.name}. Monitor stopped.")
            return

        channel_chat = bot.get_channel(channel_chat_id)
        if not channel_chat:
            print("Error: Chat channel for Steam notifications not found.")
            return

        game_name = "leer"
        print(f"Starting Steam monitor for {member.name} ({steam_id}).")

        while True:
            # Check if the user is still in the voice channel
            current_member = channel_chat.guild.get_member(member_id)
            if current_member is None or not current_member.voice or not current_member.voice.channel:
                print(f"User {member.name} is no longer in a voice channel. Stopping Steam monitor.")
                break

            data = await self.get_player_summary(steam_id)
            if data and 'gameextrainfo' in data["response"]["players"][0]:
                current_game = data["response"]["players"][0]["gameextrainfo"]
                if current_game != "leer" and current_game != game_name:
                    game_name = current_game
                    
                    # --- NEW: Dynamic replies from config.py ---
                    message = f"Have fun playing {game_name} " # Default message
                    gif = None

                    # Check for a custom reply message in config
                    if game_name in config.GAME_STEAM_REPLIES:
                        message = config.GAME_STEAM_REPLIES[game_name]
                    
                    # --- NEW: Check for game-specific GIFs from config.py ---
                    if game_name == "Halo Infinite":
                         gif = random.choice(config.HALO_GIFS)
                    elif game_name == "EA SPORTS™ FIFA 23":
                         gif = random.choice(config.FIFA_GIFS)
                    elif game_name == "Rocket League":
                         gif = random.choice(config.ROCKET_LEAGUE_GIFS)
                    elif game_name == "Counter-Strike 2":
                         gif = random.choice(config.COUNTER_STRIKE_GIFS)
                    # Add more 'elif' blocks here for other games
                    # --- End of dynamic replies ---

                    await channel_chat.send(f"{message}<@{member.id}>")
                    if gif:
                        await channel_chat.send(gif)
            
            # Wait for the poll interval
            await asyncio.sleep(STEAM_API_POLL_INTERVAL)

        if member_id in active_steam_monitors:
            del active_steam_monitors[member_id]
            print(f"Monitor task for {member.name} removed.")

steam_api_instance = SteamAPI(STEAM_API_KEY)

@bot.event
async def on_disconnect():
    if hasattr(steam_api_instance, 'session') and steam_api_instance.session is not None:
        if not steam_api_instance.session.closed:
            try:
                await steam_api_instance.session.close()
                print("Aiohttp ClientSession closed.")
            except Exception as e:
                print(f"Error closing Aiohttp ClientSession: {e}")
    print("Bot has disconnected.")

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user.name}")
    await bot.change_presence(status=discord.Status.online, activity=activity)

    # Initialize the SteamAPI session
    await steam_api_instance.initialize_session()
    
    # Load the list of available sounds
    global SOUNDS_LIST
    SOUNDS_LIST.clear()
    if os.path.exists(SOUNDS_DIR):
        for filename in os.listdir(SOUNDS_DIR):
            if filename.endswith(('.mp3', '.wav')):
                SOUNDS_LIST.append(os.path.splitext(filename)[0])
        print(f"Loaded soundboard sounds: {', '.join(SOUNDS_LIST)}")
    else:
        print(f"Warning: Sound directory '{SOUNDS_DIR}' not found.")

@bot.event
async def on_command_error(ctx, error):
    # (Legacy error handler for prefix commands, can be removed if not used)
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(str(error))
    else:
        raise error

@bot.tree.error
async def on_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # Global error handler for slash commands
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(str(error), ephemeral=True)
    else:
        print(f"Unhandled app command error: {error} in interaction {interaction}")
        await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)

async def play_sound_in_vc(interaction: discord.Interaction, sound_name: str):
    global voice_operation_in_progress

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("You must be in a voice channel to use this!", ephemeral=True)
        return

    # Check for both .wav and .mp3
    sound_path_wav = os.path.join(SOUNDS_DIR, f"{sound_name}.wav")
    sound_path_mp3 = os.path.join(SOUNDS_DIR, f"{sound_name}.mp3")
    
    selected_sound_path = None
    if os.path.exists(sound_path_wav):
        selected_sound_path = sound_path_wav
    elif os.path.exists(sound_path_mp3):
        selected_sound_path = sound_path_mp3
    else:
        await interaction.followup.send(f"The sound '{sound_name}' was not found.", ephemeral=True)
        return

    if voice_operation_in_progress:
        await interaction.followup.send("I'm already playing a sound or joining a channel. Please try again shortly.", ephemeral=True)
        return
    
    voice_operation_in_progress = True
    vc = interaction.guild.voice_client

    try:
        if vc: # If bot is already in a VC
            if vc.channel.id != interaction.user.voice.channel.id:
                await interaction.followup.send(f"Switching to {interaction.user.voice.channel.name}...", ephemeral=True)
                await vc.move_to(interaction.user.voice.channel)
            else:
                if vc.is_playing():
                     await interaction.followup.send("I'm already playing a sound. Wait until it's finished.", ephemeral=True)
                     return
        else: # If bot is not in a VC
            try:
                vc = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f"An unexpected error occurred while joining: {e}", ephemeral=True)
                return

        if not vc:
            await interaction.followup.send("Could not establish a valid voice connection.", ephemeral=True)
            return
        
        # Short pause to allow Discord to update mute status
        await asyncio.sleep(0.5) 
        bot_member = interaction.guild.me
        if bot_member.voice and bot_member.voice.mute:
            print("!!!! DIAGNOSIS: Bot is SERVER-MUTED (mute=True) !!!!")
        if bot_member.voice and bot_member.voice.self_mute:
            print("!!!! DIAGNOSIS: Bot is SELF-MUTED (self_mute=True) !!!!")

        # Play the sound
        source = discord.FFmpegPCMAudio(selected_sound_path)
        vc.play(source, after=lambda e: print(f'Player error: {e}') if e else None)
        await interaction.followup.send(f"Playing sound: **{sound_name}** in **{interaction.user.voice.channel.name}**", ephemeral=False)

        # Wait until playing is finished
        while vc.is_playing():
            await asyncio.sleep(0.5)
            
    except Exception as e:
        print(f"Error while playing sound: {e}")
        await interaction.followup.send(f"An error occurred while playing the sound: {e}", ephemeral=True)
    finally:
        voice_operation_in_progress = False
        # Disconnect after playing
        if vc and vc.is_connected():
            await vc.disconnect()
            print(f"Bot left voice channel {interaction.user.voice.channel.name} (after soundboard).")

@bot.event
async def on_presence_update(before, after):
    # --- NEW: Generalized function ---
    # Ignore bots and users not in voice
    if after.bot or not after.voice or not after.voice.channel:
        return

    # Ignore if activities haven't changed
    if before.activities == after.activities:
        return

    # Load chat channel from config
    channel_chat = bot.get_channel(config.MAIN_CHANNEL_ID)
    if not channel_chat:
        print(f"Error: 'on_presence_update' could not find channel {config.MAIN_CHANNEL_ID}.")
        return

    # Iterate through user's activities
    for activity_after in after.activities:
        if isinstance(activity_after, discord.Game):
            
            # --- THE DYNAMIC PART ---
            # Check if the game name is in our config file
            if activity_after.name in config.PRESENCE_JOKES:
                
                # Get the reply from config
                reply = config.PRESENCE_JOKES[activity_after.name]
                
                # Send the reply
                await channel_chat.send(f'{reply} <@{after.id}>')

@bot.event
async def on_message(msg):
    # Respond to 'uwu' and 'nya'
    if msg.author.bot:
        return
    if "uwu" in msg.content.lower():
        await msg.channel.send("UwU!")
    elif "nya" in msg.content.lower():
        await msg.channel.send("Nyaaa~!")

@bot.event
async def on_voice_state_update(member, before, after):
    global voice_operation_in_progress
    if not assert_voice_event_cooldown():
        return
    if member.bot:
        return

    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    
    # --- NOTE: Time definitions could also be moved to config.py ---
    start_m = datetime.strptime('07:00:00', '%H:%M:%S').time()
    end_m = datetime.strptime('11:30:00', '%H:%M:%S').time()
    start_nacht = datetime.strptime('20:00:00', '%H:%M:%S').time()
    end_nacht = datetime.strptime('23:59:00', '%H:%M:%S').time()
    start_nacht2 = datetime.strptime('00:01:00', '%H:%M:%S').time()
    end_nacht2 = datetime.strptime('05:30:00', '%H:%M:%S').time()
    current_time_obj = datetime.strptime(current_time, '%H:%M:%S').time()

    # --- NEW: Load Channel ID from config.py ---
    channel_chat = bot.get_channel(config.MAIN_CHANNEL_ID)
    if not channel_chat:
        print(f"Error: Chat channel {config.MAIN_CHANNEL_ID} not found.")
        return

    # User JOINS a channel
    if before.channel is None and after.channel is not None:
        print(f"{member.name} joined voice channel {after.channel.name}.")
        
        # --- NEW: Load STEAM_IDS from config.py ---
        if member.id not in active_steam_monitors and config.STEAM_IDS.get(member.id):
            print(f"User {member.name} joined VC. Starting Steam monitor task.")
            # --- NEW: Pass Channel ID from config.py ---
            task = bot.loop.create_task(steam_api_instance.monitor_single_steam_user(member.id, config.MAIN_CHANNEL_ID))
            active_steam_monitors[member.id] = task

        # --- NEW: Load GIF lists from config.py using general names ---
        if start_m <= current_time_obj <= end_m:
            await channel_chat.send(f"Mion! <@{member.id}>") # (You can customize this text)
            await channel_chat.send(random.choice(config.GREETING_MORNING_GIFS))
        else:
            await channel_chat.send(f"Hamlo! <@{member.id}>") # (You can customize this text)
            await channel_chat.send(random.choice(config.GGREETING_DAY_GIFS))
        
        # (Your commented-out welcome sound code)
        # ...

    # User LEAVES a channel
    elif before.channel is not None and after.channel is None:
        print(f"{member.name} left voice channel {before.channel.name}.")

        if member.id in active_steam_monitors:
            print(f"User {member.name} left VC. Stopping Steam monitor task.")
            active_steam_monitors[member.id].cancel()
            del active_steam_monitors[member.id]
        
        # --- NEW: Load GIF lists from config.py using general names ---
        if (start_nacht <= current_time_obj <= end_nacht) or (start_nacht2 <= current_time_obj <= end_nacht2):
            await channel_chat.send(f"GuNa! <@{member.id}>") # (You can customize this text)
            await channel_chat.send(random.choice(config.FAREWELL_NIGHT_GIFS))
        else:
            await channel_chat.send(f"cu! <@{member.id}>") # (You can customize this text)
            await channel_chat.send(random.choice(config.FAREWELL_DAY_GIFS))

@bot.tree.command(name="witz", description="n witz")
@app_commands.checks.cooldown(1, 120, key=interaction_user_key)
async def witz(i: discord.Interaction):
    try:
        r = requests.get("https://witzapi.de/api/joke")
        r.raise_for_status()
        data = r.json()
        await i.response.send_message(data[0]["text"])
    except requests.exceptions.RequestException as e:
        print(f"Error with joke API: {e}")
        await i.response.send_message("The joke API seems to be down. Try again later!")

@bot.tree.command(name="reminder", description="Create a reminder")
@app_commands.checks.cooldown(1, 20, key=interaction_user_key)
@app_commands.describe(date="Date (YYYY-MM-DD)", time="Time (HH:MM)", message="Reminder text")
async def reminder(interaction: discord.Interaction, date: str, time: str, message: str):
    try:
        reminder_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        await interaction.response.send_message("Invalid time format. Please use `YYYY-MM-DD HH:MM`.")
        return

    now = datetime.now()
    delta = reminder_time - now

    if delta.total_seconds() <= 0:
        await interaction.response.send_message("The specified time is in the past.")
        return

    await interaction.response.send_message(
        f"Reminder set for {reminder_time.strftime('%Y-%m-%d %H:%M')}.")

    await asyncio.sleep(delta.total_seconds())

    # --- NEW: Load Channel ID from config.py ---
    channel_chat = bot.get_channel(config.MAIN_CHANNEL_ID)
    if channel_chat:
        await channel_chat.send(
            f"{interaction.user.mention}, you wanted to be reminded of: **{message}**, Nyan~"
        )
    else:
        try:
            await interaction.user.send(f"Your reminder: **{message}**, Nyan~ (I couldn't find the channel, so here's a DM.)")
        except discord.Forbidden:
            print(f"Could not send reminder to {interaction.user.name} (channel not found and DMs closed).")

@bot.tree.command(name="choose", description="Bot randomly chooses an option (separate options with space)")
@app_commands.checks.cooldown(1, 10, key=interaction_user_key)
async def choose(i: discord.Interaction, optionen:str):
    options_list = [opt.strip() for opt in optionen.split()]
    if not options_list:
        await i.response.send_message("Please provide options separated by spaces.", ephemeral=True)
        return
    await i.response.send_message(random.choice(options_list))

@bot.tree.command(name="playsound", description="Plays a selected sound in your voice channel.")
# --- NEW: Load role name from config.py ---
@app_commands.checks.has_any_role(config.SOUND_ROLE_NAME)
@app_commands.describe(sound="The sound you want to play")
async def playsound_command(interaction: discord.Interaction, sound: str):
    await interaction.response.defer(ephemeral=True)
    await play_sound_in_vc(interaction, sound)

# Autocomplete function for the /playsound command
@playsound_command.autocomplete("sound")
async def sound_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=sound_name, value=sound_name)
        for sound_name in SOUNDS_LIST if current.lower() in sound_name.lower()
    ][:25] # Return max 25 choices  

@bot.tree.command(name="sync", description="Synchronizes slash commands (Admin Only).")
@app_commands.checks.has_permissions(administrator=True)
async def sync_commands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    print("Starting manual sync of slash commands...")
    try:
        # --- NEW: Load Guild ID from config.py ---
        guild_obj = discord.Object(id=config.GUILD_ID)
        synced = await bot.tree.sync(guild=guild_obj)

        await interaction.followup.send(f"Successfully synced {len(synced)} commands for guild {config.GUILD_ID}.", ephemeral=True)
        print(f"Manual sync successful: {len(synced)} commands synced.")

    except Exception as e:
        await interaction.followup.send(f"An unexpected error occurred during sync: {e}", ephemeral=True)
        print(f"Unexpected error during sync: {e}")
        import traceback
        traceback.print_exc()

    sys.stdout.flush()

# Function to run a simple health check server for cloud deployments
def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind(('0.0.0.0', port))
        sock.listen(1)
        print(f"Health check server listening on 0.0.0.0:{port}")
    except Exception as e:
        print(f"Failed to bind health check server on port {port}: {e}")
        return 

    while True:
        try:
            conn, addr = sock.accept()
            conn.close()
        except Exception as e:
            print(f"Health check server error during accept/close: {e}")
            time.sleep(1)

# Run the health check server in a separate thread
health_thread = threading.Thread(target=run_health_check_server, daemon=True)
health_thread.start()

# Start the bot
if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print("Error: DISCORD_TOKEN environment variable not set.")