# ⚠️Currently in the process of ORGANIZING the GitHub repository!

# Clue-Less
Simplified version of board game Clue

# Overview
1. Features [#Features]

## Features
### Login/Logout:
    Players authenticate and join Game 1,
    with logout deactivating their Player instance.

* Chatting:

* Lobby:
    - Character Assignment:
        Unique characters assigned on first login,
        preserved across logouts (stored in game.players and game.players_list).

* Movement:
    Click adjacent rooms or hallways to move;
    all players can move freely without turn restrictions, with updates synced via WebSocket.

* Suggestion

* Accusation

* GUI:
    * Board Display:
        5x5 grid shows all players’ positions, active or inactive.
        This allows the game to continue even when some players log out.

# Tech Overview

## Backend

## Frontend


## Installation
* The commands below are based on macOS. Modify them to match your development environment.
1. Install dependencies (Python version 3.10.16)
    1. % cd move-to-the-root-of-the-project-directory
    2. Create virtual environment
        - % python -m venv myenv
    3. Activate virtual environment
        - MacOS: % source venv/bin/activate
        - Windows: file-path> venv\Scripts\activate
        - When the virtual environment is activated, (venv) appears at the beginning of the terminal prompt
    4. Install all dependencies for the Python project
        - % pip install -r requirements.txt
        * Reference: Customized code to uninstall all dependencies
            - % python uninstall_packages.py
2. DB migration
    1. Creates blueprints (migration files) for your database based on models.py
        - % python manage.py makemigrations
    2. Apply all migrations
        - % python manage.py migrate

## Run the server
    1. Run Redis server
        - % `redis-server`
    2. Initial Setup for Django Server
        * To run the server listens both HTTP (pages) and WebSocket (live) connections.
        1. Using daphne to force ASGI, ensuring WebSockets work for multiplayer functionality
            - % `python run_daphne.py`
            * This customized code improves developer efficiency by truncating the command each time the server starts.
            [For further explanation](https://hyunjinkimdeveloper.notion.site/Clue-Less-1a421801a53980059dbcc9c29b1b382f#1a821801a53980b39c8ced3d368ff56d).
        2. Close currently running server: Ctrl + c
    3. Run Django server
        - % `python manage.py runserver`
        * The server log displays: “Starting ASGI/Daphne version 4.1.2 development server at http://127.0.0.1:8000/"
    4. Running the Server in a Production Environment
        4-1. Initial Setup for Ngrok
            1. Install Ngrok
            2. Set Authentication Token at [the bottom of this page](https://dashboard.ngrok.com/get-started/your-authtoken)
            3. Authenticate my Ngrok agent
                - % `ngrok config add-authtoken $YOUR_AUTHTOKEN`
        4-2. Run Ngrok: Start the tunnel
        - %`ngrok http 8000`
        4-3. Update Settings.py
            - `PRODUCTION = True`
            - `PRODUCTION_NGROK_APP = '*.ngrok-free.app'`

### Instructions After Cloning the Repository

After cloning the repository, you may see the following system log:
>  *"_You have 18 unapplied migration(s). Your project may not work properly until you apply the migrations for app(s): admin, auth, contenttypes, sessions.
>  Run 'python manage.py migrate' to apply them._"*

This occurs because I intentionally **did not** inclulde `game/migrations` to prevent one person's database from affecting other's work.
### Initial Migration Setup
```sh
python manage.py makemigrations
python manage.py migrate
```


## [The Development Log](https://hyunjinkimdeveloper.notion.site/Clue-Less-1a421801a53980059dbcc9c29b1b382f?pvs=4) provides detailed explanations.


## Directory Tree (based on skeletal increment system)
* Project Naming Conventions
    - This project follows Python's PEP 8 naming conventions for consistency and readability:
        - Variables & functions: lower_case_with_underscores
        - Constants: ALL_CAPS_WITH_UNDERSCORES
        - Classes: PascalCase
        - Modules & directories: lower_case_with_underscores
        - Private members: _single_leading_underscore
    - For more details, refer to the [PEP 8 Style Guide](https://peps.python.org/pep-0008/#naming-conventions).
```
clue-less/
├── manage.py              # Django's command-line utility for administrative tasks
├── requirements.txt       # Lists project dependencies (Django, Channels, etc.)
├── README.md              # Project overview, setup, and feature documentation
├── clueless/             # Main Django project directory
│   ├── __init__.py       # Marks directory as a Python package
│   ├── asgi.py           # ASGI entry point for Channels (WebSocket support)
│   ├── settings.py       # Project configuration (database, apps, Channels setup)
│   ├── urls.py           # Root URL routing for the project
│   └── wsgi.py           # WSGI entry point for traditional HTTP (not used with Daphne)
├── game/                 # Django app for game logic
│   ├── __init__.py       # Marks directory as a Python package
│   ├── admin.py          # Admin panel configuration (auto-generated, optional, currently minimal)
│   ├── apps.py           # App configuration (auto-generated)
│   ├── constants.py      # Game constants (SUSPECTS, ROOMS, etc.)
│   ├── consumers.py      # WebSocket consumer for real-time game updates
│   ├── management/       # Customized testing codes
│   │   ├── __init__.py   # Marks directory as a Python package
│   │   └── commands/
│   │       ├── delete_all_players.py   # Run the script: python manage.py delete_all_players
│   │       ├── logout_all_players.py
│   │       └── print_all_users.py
│   ├── migrations/       # Database migration files
│   │   ├── __init__.py   # Marks directory as a Python package
│   │   └── 0001_initial.py  # Initial migration for Game/Player models
│   ├── models.py         # Database models (Game, Player)
│   ├── templates/        # HTML templates
│   │   └── game/         # Subdirectory for game-related templates
│   │       ├── game.html  # Main game page with board and movement
│   │       └── login.html # Login/signup page
│   ├── routing.py        # WebSocket Routing
│   ├── tests.py          # Unit tests (auto-generated, currently minimal)
│   ├── views.py          # HTTP view functions (login, game, logout)
│   └── urls.py           # App-specific URL routing
├── uninstall_packages.py # Uninstall all packages in the virtual environment
└── run_daphne.py         # Custom script to start the Daphne server with predefined settings, bypassing the command-line daphne invocation.
```

## Demo Video
### Target Increment System
[![Target Demo Video](https://img.youtube.com/vi/Hu95HgFbrEo/0.jpg)](https://youtu.be/Hu95HgFbrEo)
### Minimal Increment System
[![Minimal Demo Video](https://img.youtube.com/vi/QRNJgaIlQss/0.jpg)](https://youtu.be/QRNJgaIlQss)
### Skeletal Increment System
[![Skeletal Demo Video](https://img.youtube.com/vi/YRgRJy2u2Jk/0.jpg)](https://youtu.be/YRgRJy2u2Jk)
