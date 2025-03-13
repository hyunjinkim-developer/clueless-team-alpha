# List of playable characters in the game
SUSPECTS = [
    "Miss Scarlet", "Prof. Plum", "Mrs. Peacock", "Mr. Green", "Mrs. White", "Col. Mustard"
]

# List of rooms on the game board
ROOMS = [
    "Study", "Hall", "Lounge",
    "Library", "Billiard Room", "Dining Room",
    "Conservatory", "Ballroom", "Kitchen"
]

# List of weapons available in the game
WEAPONS = [
    "Rope", "Lead Pipe", "Knife", "Wrench", "Candlestick", "Revolver",
]

# List of hallways connecting rooms, with descriptive comments
HALLWAYS = [
    "Hallway1",  # Connects Study & Hall
    "Hallway2",  # Connects Lounge & Hall
    "Hallway3",  # Connects Study & Library
    "Hallway4",  # Connects Billiard Room & Hall
    "Hallway5",  # Connects Lounge & Dining Room
    "Hallway6",  # Connects Billiard Room & Library
    "Hallway7",  # Connects Billiard Room & Dining Room
    "Hallway8",  # Connects Conservatory & Library
    "Hallway9",  # Connects Billiard Room & Ballroom
    "Hallway10", # Connects Kitchen & Dining Room
    "Hallway11", # Connects Conservatory & Ballroom
    "Hallway12", # Connects Kitchen & Ballroom
]

# Starting locations for each character at the beginning of the game
STARTING_LOCATIONS = {
    "Miss Scarlet": "Hallway2",
    "Prof. Plum": "Hallway3",
    "Mrs. Peacock": "Hallway8",
    "Mr. Green": "Hallway11",
    "Mrs. White": "Hallway12",
    "Col. Mustard": "Hallway5",
}

# Adjacency map defining valid moves between rooms and hallways
ADJACENCY = {
    # Rooms and their adjacent hallways
    'Study': ['Hallway1', 'Hallway3', 'Kitchen'],  # Secret passage to Kitchen
    'Hall': ['Hallway1', 'Hallway2', 'Hallway4'],
    'Lounge': ['Hallway2', 'Hallway5', 'Conservatory'], # Secret passage to Conservatory
    'Library': ['Hallway3', 'Hallway6', 'Hallway8'],
    'BilliardRoom': ['Hallway4', 'Hallway6', 'Hallway7', 'Hallway9'],
    'DiningRoom': ['Hallway5', 'Hallway7', 'Hallway10'],
    'Conservatory': ['Hallway8', 'Hallway11', 'Lounge'],  # Secret passage to Lounge
    'Ballroom': ['Hallway9', 'Hallway11', 'Hallway12'],
    'Kitchen': ['Hallway10', 'Hallway12', 'Study'],  # Secret passage to Study
    # Hallways and their adjacent rooms
    'Hallway1': ['Study', 'Hall'],
    'Hallway2': ['Hall', 'Lounge'],
    'Hallway3': ['Study', 'Library'],
    'Hallway4': ['Hall', 'BilliardRoom'],
    'Hallway5': ['Lounge', 'DiningRoom'],
    'Hallway6': ['Library', 'BilliardRoom'],
    'Hallway7': ['BilliardRoom', 'DiningRoom'],
    'Hallway8': ['Library', 'Conservatory'],
    'Hallway9': ['BilliardRoom', 'Ballroom'],
    'Hallway10': ['DiningRoom', 'Kitchen'],
    'Hallway11': ['Conservatory', 'Ballroom'],
    'Hallway12': ['Ballroom', 'Kitchen']
}