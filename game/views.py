from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django import forms
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import random

from .models import *
from .constants import *

# Custom form for user signup
class SignupForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)  # Username field with max length 150
    password = forms.CharField(widget=forms.PasswordInput, required=True)  # Password field with hidden input

# View to handle login and signup
def login_view(request):
    if request.method == 'POST':
        if 'login' in request.POST:
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                # Ensure a game with ID 1 exists, or create one
                game, created = Game.objects.get_or_create(id=1, defaults={'case_file': {}})
                # If this is a new game, initialize the case file
                if created:
                    game.case_file = {
                        'suspect': random.choice(SUSPECTS),
                        'room': random.choice(ROOMS),
                        'weapon': random.choice(WEAPONS)
                    }
                    game.save()
                # Assign a random character to the user
                assign_random_character(game, user)
                return redirect('game_view', game_id=game.id)
        elif 'signup' in request.POST:
            form = SignupForm(request.POST)
            if form.is_valid():
                username = form.cleaned_data['username']
                password = form.cleaned_data['password']
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(username=username, password=password)
                    login(request, user)
                    # Ensure a game with ID 1 exists, or create one
                    game, created = Game.objects.get_or_create(id=1, defaults={'case_file': {}})
                    # If this is a new game, initialize the case file
                    if created:
                        game.case_file = {
                            'suspect': random.choice(SUSPECTS),
                            'room': random.choice(ROOMS),
                            'weapon': random.choice(WEAPONS)
                        }
                        game.save()
                    # Assign a random character to the user
                    assign_random_character(game, user)
                    return redirect('game_view', game_id=game.id)
                else:
                    form.add_error('username', 'Username already exists.')
        else:
            form = AuthenticationForm() if 'login' in request.GET else SignupForm()
    else:
        form = AuthenticationForm() if 'login' not in request.GET else SignupForm()
    return render(request, 'game/login.html',
                  {'form': form, 'show_signup': 'signup' in request.GET})

# View to handle user logout
def logout_view(request):
    logout(request)  # Log the user out
    return redirect('login')  # Redirect to login page

def game_view(request, game_id):
    if not request.user.is_authenticated:
        return redirect('login')
    game = Game.objects.get(id=game_id)
    players = list(game.players.values('username', 'character', 'location', 'turn', 'hand'))
    return render(request, 'game/game.html', {
        'game_id': game_id,
        'players': players  # Pass players data to template
    })

def assign_random_character(game, user):
    """
    Assign a random character to the user for the given game, ensuring no duplicates.
    """
    # Get the list of characters already taken in the game
    taken_characters = game.players.values_list('character', flat=True)
    available_characters = [char for char in SUSPECTS if char not in taken_characters]
    if not available_characters:
        raise ValueError("No available characters left in the game.")

    # Randomly select a character from the available ones
    character = random.choice(available_characters)

    # Create or update the Player object for the user in the game
    player, created = Player.objects.get_or_create(
        game=game,
        username=user.username,  # Renamed from nickname
        defaults={
            'character': character,
            'location': STARTING_LOCATIONS[character],
            'is_active': True,
            'turn': character == "Miss Scarlet"
        }
    )

    if not created:
        # If the player already exists, update their character and location
        player.character = character
        player.location = STARTING_LOCATIONS[character]
        player.is_active = True
        player.turn = character == "Miss Scarlet"
        player.save()

    # Notify all players of the updated game state via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"game_{game.id}",
        {
            'type': 'game_update',
            'game_state': get_game_state(game)
        }
    )

def get_game_state(game):
    """
        Helper function to get the current game state for broadcasting.
    """
    players = list(game.players.values('username', 'character', 'location', 'turn', 'hand'))
    return {
        'case_file': game.case_file if not game.is_active else None,
        'players': players,
        'is_active': game.is_active,
        'rooms': ROOMS,
        'hallways': HALLWAYS,
        'weapons': WEAPONS
    }


