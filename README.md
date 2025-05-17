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

### In-Game Chat

- Players can communicate via the built-in chat to coordinate and decide when to start the game.
- Once a player joins, they can send messages that are broadcast to all other players in the game.
- My messages appear on the right, while messages from other players are displayed on the left alongside their profile images.
  ![](./static/readme/chat_result.jpeg)

- Tested across multiple devices and browsers:<br>
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

### Lobby

- When players enter the lobby, the server generates a Case File (suspect, room, weapon) and distributes cards.
- A broadcast message is sent to all players when someone joins, updating the player list and count.
- The game can start once **3 to 6 players** have joined.
- Mrs. Scarlet becomes the host if assigned; otherwise, due to random character assignment, the first player to join is designated as host and can start the game.
  ![](./static/readme/lobby.gif)

### Player Movement & Turn Rules

- The player's username, character name, and their character name displayed on the board are highlighted in yellow.
- Players can move between rooms and hallways, including secret diagonal passages, by clicking the target location.

  - Movement through secret hallways
    ![](./static/readme/movement_secret_hallway.gif)
  - Movement from hallways to rooms
    ![](./static/readme/movement_hallway_to_room.gif)

- Errors are displayed if:

  - The player is already at the selected location,
    ![](./static/readme/movement_error_same_location.gif)
  - The move is invalid,
    ![](./static/readme/movement_error_invalid_location.gif)
  - Or the target hallway is occupied.
    ![](./static/readme/movement_error_occupied_hallway.gif)

- A player's turn ends when they click the End Turn button.
  ![](./static/readme/end_turn.gif)
  - Players can move only during their turn.
    ![](./static/readme/movement_error_not_my_turn.gif)

### Suggestion

- Players can only make a suggestion during their turn; attempting to do so on another player's turn will trigger an error message.
- Players can only make a suggestion when they are in a room;
  - !attempting to do so in a hallway
  - !Move to a room and make a suggestion after choosing suspect and weapon.
- Display cards in hand with Display Hand button
- -> ! based on what's in hand, submit suggestion
- -> ! Multiple cards to disprove, choose one among them
- Emliminated character because of false accusation
  - could still moved thorough a suggestion
  - could still disprove suggestion

### Accusation

- Player can make an accusation any point during the game.
- ! Make accusation right after login
- Players can only make an accusation during their turn; attempting to do so on another player's turn will trigger an error message.
- ! Check error message style

- If an accusation is incorrect,

  - the system privately notify the accusing player an message “Your accusation was incorrect. You are no longer able to move or make accusations, but you remain a suspect.” and broadcast 'Player 1 has been eliminated due to an incorrect accusation.'"
  - ! Move and make accusation
  - ! two notification doesn't overlap

  - The eliminated player can no longer move, their turn automatically skipped, and the "End Turn" button is disabled.
    - ! Click button
  - The eliminated player is no longer eligible to win and cannot make accusations as "Accusations" button is disabled.
    - ! Click button
  - The eliminated player cannot make suggestions as "Suggestions" button is disabled.
    - ! Click button
  - The eliminated player still Can prove opponents' suggestions false.

    - ! "Display Hand" should not be disabled

  - When only one player reamins because all other players have been eliminated due to incorrect accusations,

    - The last player continues taking turns alone, ensuring the game reaches completion.

  - Tie: If all players make incorrect accusations,
    - the system disables the accusations buttons for all players,
    - broadcast the game ending in a tie, and shows a distinct notification style when the game ends

- If an accusation is correct,
- Show notifications in title differently after the game ends with a winner or ends in a tie

### Game History

- ! Modify button size and style,
- ! Check Light/Dark mode (low prio.)

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
  - Supports **up to 6 players** per game; a 7th player attempting to join receives an error message.
    ![](./static/readme/exceed_6players.gif)
- Logout
  - Logging out deactivates the player's game instance.

### GUI:

- Light/Dark Mode for user convenience, ensuring consistent styling throughout the entire game interface.
- All game messages are displayed as 7-second popups for clarity and consistency.

## Installation

This project is based on **Python version 3.10.16**. The commands below are based on macOS.
Modify these settings to suit your development environment.

1. Move to the root of the project directory

   ```sh
   % cd path/to/your/project-directory
   ```

2. Create virtual environment (both MacOS and Windows)

   ```sh
   % python -m venv venv
   ```

3. Activate virtual environment

   - MacOS:
     ```sh
     % source venv/bin/activate
     ```
   - Windows:
     ```sh
     file-path> .\venv\Scripts\activate
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

- Branches were intentionally retained to reflect unmerged or externally merged contributions, indicate code ownership, and help teammates better understand the project history.
- Testing code is in `/game/management/commands/`, with usage and purpose explained in each command's help section.
