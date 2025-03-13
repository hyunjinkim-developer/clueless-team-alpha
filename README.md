# Clue-Less
Simplified version of board game Clue

## Run the server
- The commands below are based on macOS. Modify them to match your development environment.
1. Install dependencies (Python version 3.10.16)
% cd move-to-the-root-of-project-directory
% activate-virtual-environment
% pip install -r requirements.txt
    - To uninstall all dependencies
    % python uninstall_packages.py
2. Run the server
    1-1. Run Redis server
        % redis-server
    1-2. Setting for ASGI/Channels
        % python run_daphne.py
        - To run the server listens both HTTP (pages) and WebSocket (live) connections.
            You can see why it is needed and how it works on https://www.notion.so/hyunjinkimdeveloper/Clue-Less-1a421801a53980059dbcc9c29b1b382f#1a821801a53980b39c8ced3d368ff56d
    1-3. Run Django server
        % python manage.py runserver
        - Server log shows “Starting ASGI/Daphne version [version] development server at [url]”
- Development Log
    The development log contains debugging cases
    You can track updates on [https://hyunjinkimdeveloper.notion.site/Clue-Less-1a421801a53980059dbcc9c29b1b382f?pvs=4]

## Directory

## Features

## Task-list
* When reload the page,
    - show corresponding data not overwritten with the latest login player info
    - Consider deployment on cloud services


