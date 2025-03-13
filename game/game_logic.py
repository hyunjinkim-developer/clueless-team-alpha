import random
from .constants import *


def generate_case_file():
    suspect = random.choice(SUSPECTS)
    weapon = random.choice(WEAPONS)
    room = random.choice(ROOMS)
    return {"suspect": suspect, "room": room, "weapon": weapon}


def generate_hands(case_file, players):
    combined_list = SUSPECTS + WEAPONS + ROOMS
    remaining_cards = [item for item in combined_list if item not in case_file.values()]
    random.shuffle(remaining_cards)

    num_players = len(players)
    if num_players == 0:
        raise ValueError("No players in the game.")

    hands = {player: [] for player in players}
    player_list = list(players)
    current_player_index = 0

    while remaining_cards:
        hands[player_list[current_player_index]].append(remaining_cards.pop(0))
        current_player_index = (current_player_index + 1) % num_players

    return hands


def set_player_info(game, nickname, character):
    if any(p.character == character for p in game.players.all()):
        raise ValueError(f"Character {character} is already taken.")

    player = game.players.create(
        nickname=nickname,
        character=character,
        location=STARTING_LOCATIONS[character],
        is_active=True,
        turn=(character == "Miss Scarlet")
    )
    return player