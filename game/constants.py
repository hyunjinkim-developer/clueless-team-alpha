SUSPECTS = [
    "Miss Scarlet", "Prof. Plum", "Mrs. Peacock", "Mr. Green", "Mrs. White", "Col. Mustard"
]

ROOMS = [
    "Study", "Hall", "Lounge",
    "Library", "Billiard Room", "Dining Room",
    "Conservatory", "Ballroom", "Kitchen"
]

WEAPONS = [
    "Rope", "Lead Pipe", "Knife", "Wrench", "Candlestick", "Revolver",
]

HALLWAYS = [
    "Hallway1", # "Study & Hall Hallway"
    "Hallway2", # "Lounge & Hall Hallway"
    "Hallway3", # "Study & Library Hallway"
    "Hallway4", # "Billiard Room & Hall Hallway"
    "Hallway5", # "Lounge & Dining Room Hallway"
    "Hallway6", # "Billiard Room & Library Hallway"
    "Hallway7", # "Billiard Room & Dining Room Hallway"
    "Hallway8", # "Conservatory & Library Hallway"
    "Hallway9", # "Billard Room & Ballroom Hallway"
    "Hallway10", # "Kitchen & Dining Room Hallway"
    "Hallway11", # "Conservatory & Ballroom Hallway"
    "Hallway12", # "Kitchen & Ballroom Hallway"
]

STARTING_LOCATIONS = {
    "Miss Scarlet": "Hallway2",
    "Prof. Plum": "Hallway3",
    "Mrs. Peacock": "Hallway8",
    "Mr. Green": "Hallway11",
    "Mrs. White": "Hallway12",
    "Col. Mustard": "Hallway5",
}

ADJACENCY = {
    # Rooms and their adjacent hallways
    'Study': ['Hallway1', 'Hallway3', 'Kitchen'],
    'Hall': ['Hallway1', 'Hallway2', 'Hallway4'],
    'Lounge': ['Hallway2', 'Hallway5', 'Conservatory'],
    'Library': ['Hallway3', 'Hallway6', 'Hallway8'],
    'BilliardRoom': ['Hallway4', 'Hallway6', 'Hallway7', 'Hallway9'],
    'DiningRoom': ['Hallway5', 'Hallway7', 'Hallway10'],
    'Conservatory': ['Hallway8', 'Hallway11', 'Lounge'],
    'Ballroom': ['Hallway9', 'Hallway11', 'Hallway12'],
    'Kitchen': ['Hallway10', 'Hallway12', 'Study'],
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