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

# For debugging purpose, remove after development
DEBUG_AUTH = True

# Custom form for user signup
class SignupForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)  # Username field with max length 150
    password = forms.CharField(widget=forms.PasswordInput, required=True)  # Password field with hidden input

# View to handle login and signup
def login_view(request):
    # Initialize forms for login and signup
    login_form = AuthenticationForm()
    signup_form = SignupForm()
    # Determine whether to show signup form based on GET/POST parameters
    show_signup = 'signup' in request.GET or 'signup' in request.POST
    error_message = None  # Store error messages for display
    success_message = None  # Store success messages for display

    # Get or create Game 1 with default empty case_file and players_list
    game, _ = Game.objects.get_or_create(id=1, defaults={'case_file': {}, 'players_list': []})
    all_players = game.players_list  # List of all players who ever joined

    if request.method == 'POST':
        if 'login' in request.POST:
            # Handle login form submission
            login_form = AuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                # Check if game has reached 6 unique players and user isn’t already in players_list
                if len(game.players_list) >= 6 and user.username not in game.players_list:
                    error_message = "The game is already full with 6 players."
                else:
                    login(request, user)  # Log the user in
                    assign_random_character(game, user)  # Assign or reactivate character
                    success_message = f"Logged in successfully as {user.username}!"

                    if DEBUG_AUTH:
                        # Log all players to server console after login
                        print(f"\n--- Player Login: {user.username} ---")
                        print("All players in Game 1:")
                        for player in game.players.all():
                            print(f"Username: {player.username}, Character: {player.character}, Is Active: {player.is_active}")
                        print(f"Total players ever joined: {len(game.players_list)}")
                        print("----------------\n")

                    return redirect('game_view', game_id=game.id)  # Redirect to game page
            else:
                error_message = "Invalid login credentials."  # Display error for invalid login
        elif 'signup' in request.POST:
            # Handle signup form submission
            signup_form = SignupForm(request.POST)
            if signup_form.is_valid():
                username = signup_form.cleaned_data['username']
                password = signup_form.cleaned_data['password']
                if not User.objects.filter(username=username).exists():
                    # Create new user without auto-login
                    user = User.objects.create_user(username=username, password=password)
                    success_message = f"Signup successful for {username}! Please log in."
                    show_signup = False  # Switch back to login form
                    signup_form = SignupForm()  # Reset signup form
                else:
                    signup_form.add_error('username', 'Username already exists.')
                    error_message = "Username already exists."
            else:
                error_message = "Invalid signup details."

    # Render login page with forms and messages
    return render(request, 'game/login.html', {
        'login_form': login_form,
        'signup_form': signup_form,
        'show_signup': show_signup,
        'error_message': error_message,
        'success_message': success_message,
        'all_players': all_players
    })

# View to render the game page
def game_view(request, game_id):
    # Redirect to login if user isn’t authenticated
    if not request.user.is_authenticated:
        return redirect('login')

    # Get the game instance
    game = Game.objects.get(id=game_id)
    # Get current game state for initial render only
    game_state = get_game_state(game)
    # Render game.html with game_id and initial players data
    return render(request, 'game/game.html', {
        'game_id': game_id,
        'players': game_state['players']  # Still needed for players-data
    })

# View to handle logout
def logout_view(request):
    if request.user.is_authenticated:
        game = Game.objects.get(id=1)
        try:
            # Find and deactivate the current player
            player = Player.objects.get(game=game, username=request.user.username, is_active=True)
            player.is_active = False
            player.save()  # Player remains in players_list and on board

            if DEBUG_AUTH:
                # Log all players to server console after logout
                print(f"\n--- Player Logout: {request.user.username} ---")
                print("All players in Game 1:")
                for player in game.players.all():
                    print(f"Username: {player.username}, Character: {player.character}, Is Active: {player.is_active}")
                print(f"Total players ever joined: {len(game.players_list)}")
                print("----------------\n")

            # Broadcast updated game state, including all players
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"game_{game.id}",
                {
                    'type': 'game_update',
                    'game_state': get_game_state(game)
                }
            )
        except Player.DoesNotExist:
            pass  # Player wasn’t active or doesn’t exist
    logout(request)  # Log out the user from the session
    return redirect('login')

# Function to assign or reactivate a character for a user
def assign_random_character(game, user):
    """
    Assign a random character to the user for the given game, ensuring no duplicates.
    If the user already has a character, reactivate it without changing the character.
    """
    try:
        player = Player.objects.get(game=game, username=user.username)
        if not player.is_active:
            player.is_active = True
            player.save()  # Reactivate existing player
    except Player.DoesNotExist:
        # Assign a new character if player doesn’t exist
        taken_characters = game.players.filter(is_active=True).values_list('character', flat=True)
        available_characters = [char for char in SUSPECTS if char not in taken_characters]
        if not available_characters:
            raise ValueError("No available characters left in this game.")
        character = random.choice(available_characters)
        player = Player.objects.create(
            game=game,
            username=user.username,
            character=character,
            location=STARTING_LOCATIONS[character],  # Set initial location from constants
            is_active=True,
            turn=character == "Miss Scarlet" and game.players.filter(is_active=True).count() == 0  # First player gets turn
        )
        if user.username not in game.players_list:
            game.players_list.append(user.username)  # Add to historical list
            game.save()

    # Broadcast updated game state to all clients
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"game_{game.id}",
        {
            'type': 'game_update',
            'game_state': get_game_state(game)
        }
    )

# Function to get the current game state
def get_game_state(game):
    # Fetch all players (active or inactive) with relevant fields
    fields = [f.name for f in Player._meta.fields]  # Dynamically get all Player fields
    players = list(game.players.values(*fields))  # Fetch all fields for all players
    # Return game state dictionary for WebSocket and initial render
    return {
        'case_file': game.case_file if not game.is_active else None,
        'game_is_active': game.is_active,  # Game status
        'players': players,  # List of all players, active or not
        'rooms': ROOMS,
        'hallways': HALLWAYS,
        'weapons': WEAPONS
    }