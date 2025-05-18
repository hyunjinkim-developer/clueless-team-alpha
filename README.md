# ⚠️Currently in the process of ORGANIZING the GitHub repository!

# Clue-Less

This web application is a simplified version of the classic board game Clue®.
Clue-Less retains the same nine rooms, six weapons, and six characters as the original game.
The core rules remain unchanged, with the main simplification being how players navigate the game board.

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
    <table>
        <tr>
            <td><img src="./static/readme/iphone_safari.png" alt="iphone_safari" height="450" width=auto></td>
            <td><img src="./static/readme/iphone_safari_zoomin.jpeg" alt="iphone_safari" height="450" width=auto></td>
        </tr>
    </table>

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

- Players can only make a suggestion during their turn; attempting to do so on another player's turn triggers an error message.
  ![](./static/readme/suggestion_not_your_turn.gif)

- Suggestions can only be made when the player is inside a room (not in a hallway).
  ![](./static/readme/suggestion_move_to_room.gif)

- Players can view their own cards at any time using the Display Hand button.
  ![](./static/readme/suggestion_display_hand.gif)

- Only the suspect and weapon are specified in a suggestion; the room is implied by the player's current location.
- When a suggestion is made:

  - The suggested character is moved to the room where the suggestion is made.
  - The system checks each other player, in order, to find someone who can disprove the suggestion.
  - If a player holds multiple matching cards, they can choose which card to reveal.

  ![](./static/readme/suggestion_disprove.gif)

- Eliminated characters (due to incorrect accusations):
  - Can still disprove suggestions with matching cards.
    ![](./static/readme/suggestion_eliminated_disprove.gif)
  - Can still be moved if they are part of another player's suggestion.
    ![](./static/readme/suggestion_eliminated_moved.gif)

### Accusation

- Players can make an accusation at any point during their turn.

  - Attempting to accuse outside of their turn triggers an error message.
    ![](./static/readme/accusation_not_your_turn.gif)

- **Incorrect** Accusations:

  - The accusing player receives a private message, “Your accusation was incorrect. You are no longer able to move or make accusations, but you remain a suspect.”
  - A public message and notification announce the player's elimination.

  ![](./static/readme/accusation_incorrect.gif)

  - Eliminated players:

    - Cannot make suggestions or accusations; corresponding buttons are disabled.
    - Can no longer move; their turn is auto-skipped and the End Turn button is disabled.

    ![](./static/readme/accusation_eliminated_button_disabled.gif)

  - If all other players are eliminated, the last remaining player continues alone until the game ends.
    ![](./static/readme/accusation_only_player_left.gif)

  - **Tie** Condition:<br>
    If all players are eliminated due to incorrect accusations:

    - All action buttons (Display Hands, Suggestions, Accusations, End Turn) are disabled.
    - A distinct game-over notification is shown, indicating a tie.

    ![](./static/readme/accusation_tie.gif)

- **Correct** Accusations:

  - Broadcasts the correct solution and announces the winner to all players.
  - Displays a distict notification style to indicate the game has ended.
  - Disables all action buttons **except Game History** for all players.

  ![](./static/readme/accusation_correct.gif)

### Game History

- Displays all private and public messages relevant to each player.

![](./static/readme/game_history.gif)

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
