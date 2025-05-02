from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django import forms
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import random
import uuid
from django.db import transaction, DatabaseError
from django.http import HttpResponse
from django.contrib.sessions.models import Session
from django.middleware.csrf import get_token
from django.core.signing import Signer, BadSignature

from .models import *
from .constants import *

# For debugging purpose, disable in production
DEBUG = True  # Debug flag to enable/disable all logging
# Debugging Flag Conventions: DEBUG_<feature> or DEBUG_<method_name>
DEBUG_AUTH = False  # <feature> based: e.g., Debug flag for authentication logging
DEBUG_ASSIGN_RANDOM_CHARACTER = True  # <method> based

# Custom form for user signup
class SignupForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)  # Username field with max length 150
    password = forms.CharField(widget=forms.PasswordInput, required=True)  # Password field with hidden input

def login_view(request):
    """Handle user login with session management to prevent cookie sharing."""
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

    # Log incoming cookies for debugging
    sessionid = request.COOKIES.get('sessionid', 'None')
    session_key = request.session.session_key if request.session.session_key else 'unknown'
    clueless_session = request.COOKIES.get(f'clueless_session_{session_key}', 'None')
    clueless_browser = request.COOKIES.get(f'clueless_browser_{session_key}', 'None')
    clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')
    clueless_token = request.COOKIES.get(f'clueless_token_{session_key}', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')
    if DEBUG and DEBUG_AUTH:
        print(f"[login_view] Incoming request, sessionid: {sessionid}, clueless_session: {clueless_session}, "
              f"clueless_browser: {clueless_browser}, clueless_user: {clueless_user}, clueless_token: {clueless_token}, "
              f"csrf_token: {csrf_token}")

    # Generate unique browser ID for session isolation
    browser_id = f"{request.POST.get('username', str(uuid.uuid4()))}_{str(uuid.uuid4())}"
    signer = Signer()
    session_token = str(uuid.uuid4())  # Generate session-specific token

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
                    # Clear all cookies to prevent reuse from other sessions
                    response = HttpResponse(status=302)
                    response['Location'] = f'/game/{game.id}/'
                    for key in list(request.COOKIES.keys()):
                        response.delete_cookie(key)  # Remove all existing cookies to avoid sharing

                    # Create a new session to ensure isolation
                    with transaction.atomic():
                        request.session.flush()  # Clear any existing session data
                        request.session.create()  # Generate a new session
                        login(request, user)  # Authenticate the user
                        # Store session metadata for validation
                        request.session['expected_username'] = user.username
                        request.session['expected_session_id'] = request.session.session_key
                        request.session['browser_id'] = browser_id
                        # Create a signed token to validate session integrity
                        request.session['session_token'] = signer.sign(f"{user.username}:{request.session.session_key}:{browser_id}:{session_token}")
                        request.session.modified = True
                        request.session.save()  # Persist session to database
                        if DEBUG and DEBUG_AUTH:
                            print(f"[login_view] Session key for {user.username}: {request.session.session_key}")
                        session_exists = Session.objects.filter(session_key=request.session.session_key).exists()
                        if not session_exists:
                            if DEBUG and DEBUG_AUTH:
                                print(f"[login_view] Failed to save session {request.session.session_key} for {user.username}")
                            return render(request, 'game/error.html', {
                                'error_message': "Failed to save session. Please try logging in again."
                            }, status=500)
                        if DEBUG and DEBUG_AUTH:
                            print(f"[login_view] Session {request.session.session_key} saved successfully for {user.username}")

                    assign_random_character(game, user)  # Assign or reactivate character

                    success_message = f"Logged in successfully as {user.username}!"
                    if DEBUG and DEBUG_AUTH:
                        print(success_message)
                        print(f"\n--- Player Login: {user.username} ---")
                        print(f"Session ID: {request.session.session_key}")
                        print(f"Expected Username: {request.session.get('expected_username')}")
                        print(f"Expected Session ID: {request.session.get('expected_session_id')}")
                        print(f"Browser ID: {request.session.get('browser_id')}")
                        print(f"Session Token: {request.session.get('session_token')}")
                        print("All players in Game 1:")
                        for player in game.players.all():
                            print(
                                f"Username: {player.username}, Character: {player.character}, Is Active: {player.is_active}")
                        print(f"Total players ever joined: {len(game.players_list)}")
                        print("-----------------------")

                    # Set session-specific cookies with unique names to prevent sharing
                    response.set_cookie(f'sessionid_{request.session.session_key}', request.session.session_key,
                                        max_age=1800, httponly=True, samesite='Strict', path='/')
                    response.set_cookie('sessionid', request.session.session_key,
                                        max_age=1800, httponly=True, samesite='Strict', path='/')
                    response.set_cookie(f'clueless_session_{request.session.session_key}',
                                        request.session.session_key, max_age=1800, httponly=True, samesite='Strict',
                                        path='/')
                    response.set_cookie(f'clueless_browser_{request.session.session_key}', browser_id, max_age=1800,
                                        httponly=True, samesite='Strict', path='/')
                    response.set_cookie(f'clueless_user_{request.session.session_key}', user.username, max_age=1800,
                                        httponly=True, samesite='Strict', path='/')
                    response.set_cookie(f'clueless_token_{request.session.session_key}',
                                        request.session['session_token'], max_age=1800, httponly=True,
                                        samesite='Strict', path='/')
                    if DEBUG and DEBUG_AUTH:
                        print(
                            f"[login_view] Outgoing response, Set-Cookie: sessionid_{request.session.session_key}={request.session.session_key}; "
                            f"sessionid={request.session.session_key}; "
                            f"clueless_session_{request.session.session_key}={request.session.session_key}; "
                            f"clueless_browser_{request.session.session_key}={browser_id}; "
                            f"clueless_user_{request.session.session_key}={user.username}; "
                            f"clueless_token_{request.session.session_key}={request.session['session_token']}")
                    return response
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

    # Render login page with forms
    response = render(request, 'game/login.html', {
        'login_form': login_form,
        'signup_form': signup_form,
        'show_signup': show_signup,
        'error_message': error_message,
        'success_message': success_message,
        'csrf_token': get_token(request)
    })
    # Prevent caching to avoid stale session data
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max_age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    # Set a temporary browser ID cookie
    response.set_cookie('clueless_browser', browser_id, max_age=1800, httponly=True, samesite='Strict', path='/')
    if DEBUG and DEBUG_AUTH:
        print(f"[login_view] Outgoing response, Set-Cookie: clueless_browser={browser_id}")
    return response

def game_view(request, game_id):
    """Render game page with session validation to prevent overwrite."""
    # Retrieve session-specific cookies
    sessionid = request.COOKIES.get(f'sessionid_{request.session.session_key}' if request.session.session_key else 'sessionid', 'None')
    clueless_session = request.COOKIES.get(f'clueless_session_{request.session.session_key}' if request.session.session_key else 'clueless_session', 'None')
    clueless_browser = request.COOKIES.get(f'clueless_browser_{request.session.session_key}' if request.session.session_key else 'clueless_browser', 'None')
    clueless_user = request.COOKIES.get(f'clueless_user_{request.session.session_key}' if request.session.session_key else 'clueless_user', 'None')
    clueless_token = request.COOKIES.get(f'clueless_token_{request.session.session_key}' if request.session.session_key else 'clueless_token', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')
    if DEBUG and DEBUG_AUTH:
        print(f"[game_view] Incoming request, sessionid: {sessionid}, clueless_session: {clueless_session}, "
              f"clueless_browser: {clueless_browser}, clueless_user: {clueless_user}, clueless_token: {clueless_token}, "
              f"csrf_token: {csrf_token}")

    if not request.user.is_authenticated:
        if DEBUG and DEBUG_AUTH:
            print(f"Unauthenticated user attempted to access game {game_id}")
        return render(request, 'game/error.html', {
            'error_message': "You are not authenticated. Please log in."
        }, status=403)

    # Validate that the session ID matches the cookie to detect shared cookies
    if sessionid != request.session.session_key:
        if DEBUG and DEBUG_AUTH:
            print(f"[game_view] Session ID mismatch: Expected sessionid_{request.session.session_key}={request.session.session_key}, Got sessionid={sessionid}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Invalid session ID. Please log in again."
        }, status=403)

    # Ensure the session exists in the database
    if not Session.objects.filter(session_key=request.session.session_key).exists():
        if DEBUG and DEBUG_AUTH:
            print(f"[game_view] Session {request.session.session_key} does not exist")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Session expired or invalid. Please log in again."
        }, status=403)

    # Validate the session token to ensure session integrity
    expected_token = request.session.get('session_token')
    signer = Signer()
    if clueless_token != 'None' and expected_token:
        try:
            unsigned_token = signer.unsign(clueless_token)
            token_username, token_session_key, token_browser_id, token_session_token = unsigned_token.split(':')
            if token_username != request.user.username or token_session_key != request.session.session_key or \
               token_browser_id != request.session.get('browser_id'):
                if DEBUG and DEBUG_AUTH:
                    print(f"[game_view] Token validation failed: Expected username={request.user.username}, "
                          f"session_key={request.session.session_key}, browser_id={request.session.get('browser_id')}, "
                          f"Got username={token_username}, session_key={token_session_key}, browser_id={token_browser_id}")
                logout(request)
                request.session.flush()
                return render(request, 'game/error.html', {
                    'error_message': "Invalid session token. Please log in again."
                }, status=403)
        except (BadSignature, ValueError):
            if DEBUG and DEBUG_AUTH:
                print(f"[game_view] Invalid token signature or format: clueless_token={clueless_token}")
            logout(request)
            request.session.flush()
            return render(request, 'game/error.html', {
                'error_message': "Invalid session token signature. Please log in again."
            }, status=403)

    # Validate user cookie
    if clueless_user != 'None' and request.user.username != clueless_user:
        if DEBUG and DEBUG_AUTH:
            print(f"[game_view] User cookie mismatch: Expected user={request.user.username}, Got clueless_user={clueless_user}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Invalid user cookie. Please log in again."
        }, status=403)

    # Validate expected username
    expected_username = request.session.get('expected_username')
    if expected_username and request.user.username != expected_username:
        if DEBUG and DEBUG_AUTH:
            print(f"[game_view] Username mismatch: Expected username={expected_username}, Got username={request.user.username}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Session mismatch detected. Please log in again."
        }, status=403)

    # Validate browser ID
    expected_browser_id = request.session.get('browser_id')
    if not expected_browser_id:
        if DEBUG and DEBUG_AUTH:
            print(f"[game_view] Missing expected browser ID: expected_browser_id={expected_browser_id}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Missing browser ID in session. Please log in again."
        }, status=403)
    if clueless_browser != expected_browser_id:
        if DEBUG and DEBUG_AUTH:
            print(f"[game_view] Browser cookie mismatch: Expected browser_id={expected_browser_id}, Got clueless_browser={clueless_browser}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Invalid browser cookie. Please log in again."
        }, status=403)

    # Validate session cookie
    expected_session_id = request.session.get('expected_session_id')
    if clueless_session != 'None' and expected_session_id and clueless_session != expected_session_id:
        if DEBUG and DEBUG_AUTH:
            print(f"[game_view] Session cookie mismatch: Expected session_id={expected_session_id}, Got clueless_session={clueless_session}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Invalid session cookie. Please log in again."
        }, status=403)

    # Validate game existence and redirect if not started
    try:
        game = Game.objects.get(id=game_id)
    except Game.DoesNotExist:
        if DEBUG and DEBUG_AUTH:
            print(f"Game {game_id} not found")
        return render(request, 'game/error.html', {
            'error_message': "Game not found."
        }, status=404)

    if not game.begun:
        return redirect('start_game', game_id=game_id)

    # Retrieve game state for rendering
    game_state = get_game_state(game)
    # Validate player existence and status
    try:
        player = Player.objects.get(game=game, username=request.user.username)
        if not player.is_active:
            if DEBUG and DEBUG_AUTH:
                print(f"Reactivating player {request.user.username} in game {game_id}")
            player.is_active = True
            player.save()
            # Broadcast updated game state via WebSocket, relevant for reload-triggered player_out messages
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"game_{game.id}",
                {
                    'type': 'game_update',
                    'game_state': get_game_state(game)
                }
            )
    except Player.DoesNotExist:
        if request.user.username in game.players_list:
            if DEBUG and DEBUG_AUTH:
                print(f"Player {request.user.username} in players_list but no Player object, reassigning...")
            assign_random_character(game, request.user)
            try:
                player = Player.objects.get(game=game, username=request.user.username)
            except Player.DoesNotExist:
                if DEBUG and DEBUG_AUTH:
                    print(f"Failed to reassign player {request.user.username} in game {game_id}")
                return render(request, 'game/error.html', {
                    'error_message': "Unable to assign a player. The game may be full or an error occurred."
                }, status=403)
        else:
            if DEBUG and DEBUG_AUTH:
                print(f"User {request.user.username} not in players_list for game {game_id}")
            return render(request, 'game/error.html', {
                'error_message': "You are not a player in this game. Please join the game."
            }, status=403)

    if DEBUG and DEBUG_AUTH:
        print(f"Rendering game view for {request.user.username} (session: {request.session.session_key}, "
              f"expected: {expected_username}, session_id: {expected_session_id}, browser_id: {expected_browser_id}) "
              f"as {player.character} in game {game_id}")

    # Render game page
    response = render(request, 'game/game.html', {
        'game_id': game_id,
        'players': game_state['players'],
        'username': request.user.username,
        'character': player.character
    })
    # Prevent caching to avoid stale session data
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max_age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    # Set session-specific cookies to maintain session state
    response.set_cookie(f'sessionid_{request.session.session_key}', request.session.session_key, max_age=1800,
                        httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_session_{request.session.session_key}', request.session.session_key,
                        max_age=1800, httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_browser_{request.session.session_key}', expected_browser_id, max_age=1800,
                        httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_user_{request.session.session_key}', request.user.username, max_age=1800,
                        httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_token_{request.session.session_key}', expected_token, max_age=1800,
                        httponly=True, samesite='Strict', path='/')
    if DEBUG and DEBUG_AUTH:
        print(
            f"[game_view] Outgoing response, Set-Cookie: sessionid_{request.session.session_key}={request.session.session_key}; "
            f"clueless_session_{request.session.session_key}={request.session.session_key}; "
            f"clueless_browser_{request.session.session_key}={expected_browser_id}; "
            f"clueless_user_{request.session.session_key}={request.user.username}; "
            f"clueless_token_{request.session.session_key}={expected_token}")
    return response

def start_game(request, game_id):
    sessionid = request.COOKIES.get(
        f'sessionid_{request.session.session_key}' if request.session.session_key else 'sessionid', 'None')
    clueless_session = request.COOKIES.get(
        f'clueless_session_{request.session.session_key}' if request.session.session_key else 'clueless_session',
        'None')
    clueless_browser = request.COOKIES.get(
        f'clueless_browser_{request.session.session_key}' if request.session.session_key else 'clueless_browser',
        'None')
    clueless_user = request.COOKIES.get(
        f'clueless_user_{request.session.session_key}' if request.session.session_key else 'clueless_user', 'None')
    clueless_token = request.COOKIES.get(
        f'clueless_token_{request.session.session_key}' if request.session.session_key else 'clueless_token', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')
    if DEBUG and DEBUG_AUTH:
        print(f"[start_game] Incoming request, sessionid: {sessionid}, clueless_session: {clueless_session}, "
              f"clueless_browser: {clueless_browser}, clueless_user: {clueless_user}, clueless_token: {clueless_token}, "
              f"csrf_token: {csrf_token}")

    if not request.user.is_authenticated:
        return render(request, 'game/error.html', {
            'error_message': "You are not authenticated. Please log in."
        }, status=403)

    try:
        game = Game.objects.get(id=game_id)
    except Game.DoesNotExist:
        return render(request, 'game/error.html', {
            'error_message': "Game not found."
        }, status=404)

    # If game already started, redirect to game view
    if game.begun:
        return redirect('game_view', game_id=game_id)

    is_first_user = game.players_list[0] == request.user.username if game.players_list else False

    response = render(request, 'game/start_game.html', {
        'game_id': game_id,
        'is_first_user': is_first_user,
        'players_list': game.players_list,
        'player_count': len(game.players_list)
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    if DEBUG and DEBUG_AUTH:
        print(f"[start_game] Outgoing response, Set-Cookie: None")
    return response

def logout_view(request):
    """Handle user logout with cookie cleanup to prevent stale session issues."""
    # Log incoming cookies for debugging
    sessionid = request.COOKIES.get(f'sessionid_{request.session.session_key}' if request.session.session_key else 'sessionid', 'None')
    clueless_session = request.COOKIES.get(f'clueless_session_{request.session.session_key}' if request.session.session_key else 'clueless_session', 'None')
    clueless_browser = request.COOKIES.get(f'clueless_browser_{request.session.session_key}' if request.session.session_key else 'clueless_browser', 'None')
    clueless_user = request.COOKIES.get(f'clueless_user_{request.session.session_key}' if request.session.session_key else 'clueless_user', 'None')
    clueless_token = request.COOKIES.get(f'clueless_token_{request.session.session_key}' if request.session.session_key else 'clueless_token', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')
    if DEBUG and DEBUG_AUTH:
        print(f"[logout_view] Incoming request, sessionid: {sessionid}, clueless_session: {clueless_session}, "
              f"clueless_browser: {clueless_browser}, clueless_user: {clueless_user}, clueless_token: {clueless_token}, "
              f"csrf_token: {csrf_token}")

    if request.user.is_authenticated:
        game = Game.objects.get(id=1)
        try:
            # Deactivate the player
            player = Player.objects.get(game=game, username=request.user.username, is_active=True)
            player.is_active = False
            player.save()
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
    request.session.flush()  # Clear session data

    # Redirect to login page
    response = redirect('login')
    # Clear all session-related cookies to prevent reuse
    for key in list(request.COOKIES.keys()):
        if key.startswith('sessionid_') or key.startswith('clueless_session_') or \
                key.startswith('clueless_browser_') or key.startswith('clueless_user_') or \
                key.startswith('clueless_token_') or key == 'sessionid':
            response.delete_cookie(key, path='/')
    response.delete_cookie('clueless_session', path='/')
    response.delete_cookie('clueless_browser', path='/')
    response.delete_cookie('clueless_user', path='/')
    response.delete_cookie('clueless_token', path='/')
    response.delete_cookie('csrftoken', path='/')
    if DEBUG and DEBUG_AUTH:
        print(f"[logout_view] Outgoing response, Set-Cookie: sessionid=deleted; "
              f"clueless_session=deleted; clueless_browser=deleted; clueless_user=deleted; clueless_token=deleted; "
              f"csrftoken=deleted")
    return response

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
            if DEBUG and DEBUG_ASSIGN_RANDOM_CHARACTER:
                print(f"Reactivated player: {user.username} as {player.character}")
    except Player.DoesNotExist:
        # Use atomic transaction to prevent race conditions
        with transaction.atomic():
            # Get characters of all players who ever joined the game, regardless of is_active
            taken_characters = game.players.values_list('character', flat=True)
            available_characters = [char for char in SUSPECTS if char not in taken_characters]
            if not available_characters:
                raise ValueError("No available characters left in this game.")

            # Pick a random character
            character = random.choice(available_characters)
            # Extra safety: Verify no player (active or inactive) has this character
            # This is redundant with taken_characters but guards against rare edge cases
            if game.players.filter(character=character).exists():
                raise ValueError(f"Character {character} already assigned to a player!")
            player = Player.objects.create(
                game=game,
                username=user.username,
                character=character,
                location=STARTING_LOCATIONS[character],  # Set initial location from constants
                is_active=True,
                turn=False,
                hand=[],
                moved=False,
                accused=False,
                suggested=False
            )

            # Add user ever joined the game
            if user.username not in game.players_list:
                game.players_list.append(user.username)
                game.save()

            if DEBUG and DEBUG_ASSIGN_RANDOM_CHARACTER:
                print(f"Assigned new player: {user.username} as {character}")

    # Broadcast updated game state to all clients
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"game_{game.id}",
        {
            'type': 'game_update',
            'game_state': get_game_state(game)
        }
    )

def get_game_state(game):
    """Helper function to retrieve game state for WebSocket updates."""
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