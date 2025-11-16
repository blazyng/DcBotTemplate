# Discord Bot

A general-purpose Discord bot built with `discord.py`, featuring jokes, reminders, a soundboard, and Steam activity monitoring.

This project started as a private, hard-coded bot for a personal server and has been generalized to be configurable, allowing anyone to run their own instance by providing their own data (API keys, user IDs, GIF lists).

## ✨ Features

* **/witz**: Fetches a random German joke from `witzapi.de`.
* **/reminder**: Sets a reminder for a specific date and time.
* **/choose**: Randomly picks from a list of space-separated options.
* **/playsound**: Plays a local sound file (e.g., `.wav`, `.mp3`) in your voice channel. (Role-restricted)
* **/sync**: (Admin-Only) Synchronizes slash commands with Discord.
* **Steam Monitoring**: Tracks what users are playing on Steam (from a defined list) and announces it in chat.
* **Voice Events**: Greets users who join or leave voice channels with specific messages/GIFs based on the time of day.
* **Presence Jokes**: Responds when a user starts playing a specific, pre-configured game (like "Notepad++").
* **Health Check**: Includes a simple health check server for cloud deployments (e.g., Cloud Run, Fly.io).

## 🚀 Getting Started

### 1. Prerequisites

* Python 3.10+
* FFmpeg (required for voice/soundboard features)
* A Discord Bot Token
* A Steam API Key

### 2. Installation

1.  **Clone the repository:**

2.  **Create your configuration:**
    Copy the example configuration file. **This file is crucial.**
    ```bash
    cp config.py.example config.py
    ```
    Now, **edit `config.py`** and fill in all the required values (your `GUILD_ID`, `MAIN_CHANNEL_ID`, `STEAM_IDS`, GIF lists, etc.).

3.  **Create your environment file:**
    Create a file named `.env` in the root directory and add your secret keys:
    ```ini
    DISCORD_TOKEN=Your_Bot_Token_Goes_Here
    STEAM_API_KEY=Your_Steam_API_Key_Goes_Here
    ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Add your sounds:**
    Place your `.mp3` or `.wav` files into the `sounds/` directory.

### 3. Running the Bot

#### Locally with Python

```bash
python main.py


#### With Docker (Recommended)

1. **Build the image:**
    
    Bash
    
    ```
    docker build -t my-discord-bot .
    ```
    
2. Run the container:
    
    This command mounts your local config.py and sounds folder into the container and passes your .env file.
    
    Bash
    
    ```
    docker run -d --name discord-bot \
      --env-file ./.env \
      -v "$(pwd)/config.py":/app/config.py:ro \
      -v "$(pwd)/sounds":/app/sounds:ro \
      my-discord-bot
    ```
    

## ⚙️ Configuration

All bot specialization is handled in `config.py`. The `main.py` file remains generic.

- `GUILD_ID` / `MAIN_CHANNEL_ID`: Set the server and channel for the bot's interactions.
    
- `SOUND_ROLE_NAME`: The exact name of the role required to use `/playsound`.
    
- `STEAM_IDS`: A dictionary mapping Discord user IDs (as `int`) to their Steam64 IDs.
    
- `PRESENCE_JOKES`: A dictionary mapping game names (e.g., "Notepad++") to funny replies.
    
- `GAME_STEAM_REPLIES`: Maps specific Steam game names to custom announcement messages.
    
- **GIF Lists**: All lists for random GIFs are defined here using general names:
    
    - `GREETING_MORNING_GIFS`
        
    - `GREETING_DAY_GIFS`
        
    - `FAREWELL_NIGHT_GIFS`
        
    - `FAREWELL_DAY_GIFS`
        
    - (and game-specific lists like `COUNTER_STRIKE_GIFS`, `HALO_GIFS`, etc.)