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
    login_form = AuthenticationForm()
    signup_form = SignupForm()
    show_signup = 'signup' in request.GET or 'signup' in request.POST
    error_message = None
    success_message = None

    # Get the game and all players ever joined
    game, _ = Game.objects.get_or_create(id=1, defaults={'case_file': {}, 'players_list': []})
    all_players = game.players_list  # Full history from players_list

    if request.method == 'POST':
        if 'login' in request.POST:
            login_form = AuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                if len(game.players_list) >= 6 and user.username not in game.players_list:
                    error_message = "The game is already full with 6 players."
                else:
                    login(request, user)
                    assign_random_character(game, user)

                    success_message = f"Logged in successfully as {user.username}!"
                    # Log all players after login
                    print(f"\n--- Player Login: {user.username} ---")
                    print("All players in Game 1:")
                    for player in game.players.all():
                        print(
                            f"Username: {player.username}, Character: {player.character}, Is Active: {player.is_active}")
                    print(f"Total players ever joined: {len(game.players_list)}")
                    print("----------------\n")

                    return redirect('game_view', game_id=game.id)
            else:
                error_message = "Invalid login credentials."  # Error for invalid login
        elif 'signup' in request.POST:
            signup_form = SignupForm(request.POST)
            if signup_form.is_valid():
                username = signup_form.cleaned_data['username']
                password = signup_form.cleaned_data['password']
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(username=username, password=password)
                    success_message = f"Signup successful for {username}! Please log in."
                    show_signup = False  # Switch to login form
                    signup_form = SignupForm()  # Reset signup form
                else:
                    signup_form.add_error('username', 'Username already exists.')
                    error_message = "Username already exists."
            else:
                error_message = "Invalid signup details."  # Error for invalid signup
    return render(request, 'game/login.html', {
        'login_form': login_form,
        'signup_form': signup_form,
        'show_signup': show_signup,
        'error_message': error_message,
        'success_message': success_message,
        'all_players': all_players
    })

def game_view(request, game_id):
    # Simple view to render game page with game_id
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'game/game.html', {'game_id': game_id})

def logout_view(request):
    if request.user.is_authenticated:
        game = Game.objects.get(id=1)
        try:
            player = Player.objects.get(game=game, username=request.user.username, is_active=True)
            player.is_active = False
            player.save()  # No change to players_list

            # Log all players after logout
            print(f"\n--- Player Logout: {request.user.username} ---")
            print("All players in Game 1:")
            for player in game.players.all():
                print(f"Username: {player.username}, Character: {player.character}, Is Active: {player.is_active}")
            print(f"Total players ever joined: {len(game.players_list)}")
            print("----------------\n")

            # Broadcast updated game state
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"game_{game.id}",
                {
                    'type': 'game_update',
                    'game_state': get_game_state(game)
                }
            )
        except Player.DoesNotExist:
            pass
    logout(request)
    return redirect('login')

def assign_random_character(game, user):
    """
    Assign a random character to the user for the given game, ensuring no duplicates.
    """
    try:
        player = Player.objects.get(game=game, username=user.username)
        if not player.is_active:
            player.is_active = True
            player.save()
    except Player.DoesNotExist:
        taken_characters = game.players.filter(is_active=True).values_list('character', flat=True)
        available_characters = [char for char in SUSPECTS if char not in taken_characters]
        if not available_characters:
            raise ValueError("No available characters left in this game.")
        character = random.choice(available_characters)
        player = Player.objects.create(
            game=game,
            username=user.username,
            character=character,
            location=STARTING_LOCATIONS[character],
            is_active=True,
            turn=character == "Miss Scarlet" and game.players.filter(is_active=True).count() == 0
        )
        if user.username not in game.players_list:  # Add only on first join
            game.players_list.append(user.username)
            game.save()

    # Broadcast updated game state
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"game_{game.id}",
        {
            'type': 'game_update',
            'game_state': get_game_state(game)
        }
    )

def get_game_state(game):
    # Return game state with only active players
    players = list(game.players.filter(is_active=True).values('game', 'username', 'character', 'location', 'is_active', 'turn', 'hand'))
    return {
        'case_file': game.case_file if not game.is_active else None,
        'players': players,
        'is_active': game.is_active,
        'rooms': ROOMS,
        'hallways': HALLWAYS,
        'weapons': WEAPONS
    }