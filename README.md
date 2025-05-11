# ⚠️Currently in the process of ORGANIZING the GitHub repository!

# Clue-Less

This web application is a simplified version of the popular board game Clue®.
The main simplification is in the navigation of the game board.
In Clue-Less there are the same nine rooms, six weapons, and six characters as in the board game.
The rules are pretty much the same except for moving from room to room.

## Overview

1. [Features](#Features)
2. [Installation](#Installation)
3. [Quick Start](#Quick-Start)
4. [Tech Overview](#Tech-Overview)
5. [Presentation](#Presentation)
6. [Development Log](#DevelopmentLog)

## Features

### Access the System via Ngrok

- The Ngrok access point enables multiple players to log in from different devices and browsers,
  allowing them to join the same game from anywhere in the world.
  ![](./static/readme/access_point.gif)

### User Authentication

- Sign Up
  ![](./static/readme/signup.gif)
- Log In
  - Players authenticate and join the game.
  - Upon login, the server randomly assigns each player a unique character.
    ![](./static/readme/login.gif)
  - If a player **enters an incorrect password**, an error message is displayed.
    ![](./static/readme/incorrect_password.gif)
  - Cookie isolation is implemented to prevent session overwrites,
    ensuring each player's data remains intact even after page reloads.
    ![](./static/readme/cookie_isolation_reload.gif)
  - Supports **up to 6 players** per game.
    ![](./static/readme/exceed_6players.gif)
- Logout
  - Logging out deactivates the player's game instance.

### In-Game Chat

- Players can communicate via the built-in chat to coordinate and decide when to start the game.
- Once a player joins, they can send messages that are broadcast to all other players in the game.
- Tested across mutiple devices and browsers:<br>
  ![](./static/readme/chat_result.jpeg)

  - MacBook (Safari)
  - MacBook (Firefox)<br>
    ![](./static/readme/chat_macbook.gif)
  - iPad (Chrome)<br>
    ![](./static/readme/chat_ipad_chrome.gif)
  - Windows (Edge)<br>
    ![](./static/readme/chat_windows_edge.gif)
  - Windows (Chrome)<br>
    ![](./static/readme/chat_windows_chrome.gif)
  - iPhone (Safari)<br>
    <p float="left">
      <img src="./static/readme/iphone_safari.png" alt="iphone_safari" width="150" hieght="150">
      <img src="./static/readme/iphone_safari_zoomin.jpeg" alt="iphone_safari" width="600" hieght="400">
    </p>

### Lobby:

### Character Assignment:

- Unique characters assigned on first login,
  preserved across logouts (stored in game.players and game.players_list).

### Movement:

Click adjacent rooms or hallways to move;
all players can move freely without turn restrictions, with updates synced via WebSocket.

### Suggestion

### Accusation

- GUI:
  - Board Display:
    5x5 grid shows all players’ positions, active or inactive.
    This allows the game to continue even when some players log out.

## Installation

This project is based on **Python version 3.10.16**. The commands below are based on macOS.
Modify these settings to suit your development environment.

1. Move to the root of the project directory

   ```sh
   % cd path/to/your/project-directory
   ```

2. Create virtual environment

   ```sh
   % python -m venv myenv
   ```

3. Activate virtual environment

   - MacOS:
     ```sh
     % source venv/bin/activate
     ```
   - Windows:
     ```sh
     % file-path> venv\Scripts\activate
     ```

4. Install all dependencies for this project

   - ```sh
     % pip install -r requirements.txt
     ```
   - Custom script to uninstall all dependencies
     ```sh
     % python uninstall_packages.py
     ```

5. Initial Setup for Database Migration
   1. Generate migration files for your database based on `/game/models.py`
      ```sh
      % python manage.py makemigrations
      ```
   2. Apply all database migrations
      ```sh
      % python manage.py migrate
      ```

## Quick Start

1. Run Redis Server
   ```sh
   % redis-server
   ```
2. Initial Setup for Django Server: Run the following commands only once!

   - Run the server to handle both HTTP (pages) and WebSocket (live) connections.

   1. Use Daphne to enforce ASGI (Asynchronous Server Gateway Interface), ensuring WebSockets live connections function properly for multiplayer support.

      ```sh
      % python run_daphne.py
      ```

      - The customized code `/run_daphne.py` script enhances developer efficiency by shortening the startup command each time the server is launched.
        [For further explanation](https://hyunjinkimdeveloper.notion.site/Clue-Less-Development-Log-1a421801a53980059dbcc9c29b1b382f?pvs=4d).

   2. Shut Down the Running Server
      ```sh
      % ctrl + c
      ```

3. Run Django Server

   ```sh
   % python manage.py runserver
   ```

   - The server log shows “Starting `ASGI/Daphne` version 4.1.2 development server at http://127.0.0.1:8000/"

4. Running the server in a Production Setting
   1. Ngrok Installation and Authentication Setup
      1. Install Ngrok
      2. Set Authentication Token at [the bottom of this page](https://dashboard.ngrok.com/get-started/your-authtoken)
      3. Authenticate Ngrok agent
         ```sh
         % ngrok config add-authtoken $YOUR_AUTHTOKEN
         ```
   2. Run Ngrok: Start the tunnel
      ```sh
      % ngrok http 8000
      ```
   3. Update `/clueless/settings.py`
      - `PRODUCTION = True`
      - `PRODUCTION_NGROK_APP = '*.ngrok-free.app'`
5. Access the `PRODUCTION_NGROK_URL/login` Endpoint

## Tech Overview

### Backend

### Frontend

- HTML/ CSS / Javascript

## Presentation

### Target Increment System

[![Target Demo Video](https://img.youtube.com/vi/fOyfSLnUSaQ/0.jpg)](https://youtu.be/fOyfSLnUSaQ)

### Minimal Increment System

[![Minimal Demo Video](https://img.youtube.com/vi/QRNJgaIlQss/0.jpg)](https://youtu.be/QRNJgaIlQss)

### Skeletal Increment System

[![Skeletal Demo Video](https://img.youtube.com/vi/YRgRJy2u2Jk/0.jpg)](https://youtu.be/YRgRJy2u2Jk)

## Development Log

### [Development Log](https://hyunjinkimdeveloper.notion.site/Clue-Less-1a421801a53980059dbcc9c29b1b382f?pvs=4) provides detailed explanations of the system architecture, resolved issues, and their solutions, among other information.
