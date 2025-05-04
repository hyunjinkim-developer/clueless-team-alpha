# Django imports for views, authentication, and session management
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django import forms
from django.db import transaction
from django.http import HttpResponse
from django.contrib.sessions.models import Session
from django.middleware.csrf import get_token
from django.core.signing import Signer, BadSignature
from django.conf import settings

# Channels imports for WebSocket communication
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Standard library imports
import random
import uuid

# Local imports for game models and constants
from .models import *
from .constants import *

# Debug flags for logging; disable in production
DEBUG = True  # Enables/disables all debug logging
DEBUG_AUTH = True  # Authentication-specific debug logging
DEBUG_ASSIGN_RANDOM_CHARACTER = True  # Character assignment debug logging

# Custom form for user signup
class SignupForm(forms.Form):
    """
    Form for user signup with username and password fields.
    """
    username = forms.CharField(max_length=150, required=True, help_text="Username (max 150 characters)")
    password = forms.CharField(widget=forms.PasswordInput, required=True, help_text="Password")

def login_view(request):
    """
    Handle user login and signup.
    Creates a new session, sets session-specific cookies, and ensures session isolation.
    Clears all existing cookies to prevent session overwrites.
    Validates incoming session cookies against the authenticated user to prevent session hijacking.
    """
    # Initialize login and signup forms
    login_form = AuthenticationForm()
    signup_form = SignupForm()

    # Determine whether to show signup form
    show_signup = 'signup' in request.GET or 'signup' in request.POST
    error_message = None
    success_message = None

    # Get or create Game 1 with default empty case_file and players_list
    game, _ = Game.objects.get_or_create(id=1, defaults={'case_file': {}, 'players_list': []})
    all_players = game.players_list

    # Log incoming cookies for debugging
    sessionid = request.COOKIES.get('sessionid', 'None')
    session_key = request.session.session_key if request.session.session_key else 'unknown'
    clueless_session = request.COOKIES.get(f'clueless_session_{session_key}', 'None')
    clueless_browser = request.COOKIES.get(f'clueless_browser_{session_key}', 'None')
    clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')
    clueless_token = request.COOKIES.get(f'clueless_token_{session_key}', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')
    if DEBUG and DEBUG_AUTH:
        print("[login_view] Incoming request:")
        print(f"  sessionid: {sessionid}")
        print(f"  clueless_session_{session_key}: {clueless_session}")
        print(f"  clueless_browser_{session_key}: {clueless_browser}")
        print(f"  clueless_user_{session_key}: {clueless_user}")
        print(f"  clueless_token_{session_key}: {clueless_token}")
        print(f"  csrf_token: {csrf_token}")

    # Generate unique browser ID for session isolation
    browser_id = f"{request.POST.get('username', str(uuid.uuid4()))}_{str(uuid.uuid4())}"
    signer = Signer()
    session_token = str(uuid.uuid4())

    if request.method == 'POST':
        if 'login' in request.POST:
            # Handle login form submission
            login_form = AuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                # Check if game is full
                if len(game.players_list) >= 6 and user.username not in game.players_list:
                    error_message = "The game is already full with 6 players."
                else:
                    # Validate incoming session cookies against the authenticated user
                    if clueless_user != 'None' and clueless_user != user.username:
                        if DEBUG and DEBUG_AUTH:
                            print("[login_view] Cookie user mismatch:")
                            print(f"  Expected user: {user.username}")
                            print(f"  Got clueless_user: {clueless_user}")
                        # Clear all cookies and session to prevent overwrite
                        request.session.flush()
                        response = HttpResponse(status=302)
                        response['Location'] = '/login/'
                        for key in list(request.COOKIES.keys()):
                            response.delete_cookie(key, path='/')
                        return response

                    # Prepare response and clear all existing cookies
                    response = HttpResponse(status=302)
                    response['Location'] = f'/game/{game.id}/'
                    for key in list(request.COOKIES.keys()):
                        response.delete_cookie(key, path='/')

                    # Create and save new session
                    with transaction.atomic():
                        request.session.flush()
                        request.session.create()
                        login(request, user)
                        request.session['expected_username'] = user.username
                        request.session['expected_session_id'] = request.session.session_key
                        request.session['browser_id'] = browser_id
                        request.session['session_token'] = signer.sign(
                            f"{user.username}:{request.session.session_key}:{browser_id}:{session_token}")
                        request.session.modified = True
                        request.session.save()

                        # Verify session exists in database
                        session_exists = Session.objects.filter(session_key=request.session.session_key).exists()
                        if not session_exists:
                            if DEBUG and DEBUG_AUTH:
                                print("[login_view] Session save failed:")
                                print(f"  Session key: {request.session.session_key}")
                                print(f"  Username: {user.username}")
                            return render(request, 'game/error.html', {
                                'error_message': "Failed to save session. Please try logging in again."
                            }, status=500)
                        if DEBUG and DEBUG_AUTH:
                            print("[login_view] Session saved:")
                            print(f"  Session key: {request.session.session_key}")
                            print(f"  Username: {user.username}")

                    assign_random_character(game, user)

                    success_message = f"Logged in successfully as {user.username}!"
                    if DEBUG and DEBUG_AUTH:
                        print("[login_view] Login successful:")
                        print(f"  Message: {success_message}")
                        print(f"  Session ID: {request.session.session_key}")
                        print(f"  Expected Username: {request.session.get('expected_username')}")
                        print(f"  Expected Session ID: {request.session.get('expected_session_id')}")
                        print(f"  Browser ID: {request.session.get('browser_id')}")
                        print(f"  Session Token: {request.session.get('session_token')}")
                        print(f"  All players in Game 1: {[p.username for p in game.players.all()]}")
                        print(f"  Total players ever joined: {len(game.players_list)}")

                    # Set session-specific cookies
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
                        print("[login_view] Outgoing response, Set-Cookie:")
                        print(f"  sessionid: {request.session.session_key}")
                        print(f"  clueless_session_{request.session.session_key}: {request.session.session_key}")
                        print(f"  clueless_browser_{request.session.session_key}: {browser_id}")
                        print(f"  clueless_user_{request.session.session_key}: {user.username}")
                        print(f"  clueless_token_{request.session.session_key}: {request.session['session_token']}")
                    return response
            else:
                error_message = "Invalid login credentials."
        elif 'signup' in request.POST:
            # Handle signup form submission
            signup_form = SignupForm(request.POST)
            if signup_form.is_valid():
                username = signup_form.cleaned_data['username']
                password = signup_form.cleaned_data['password']
                if not User.objects.filter(username=username).exists():
                    User.objects.create_user(username=username, password=password)
                    success_message = f"Signup successful for {username}! Please log in."
                    show_signup = False
                    signup_form = SignupForm()
                else:
                    signup_form.add_error('username', 'Username already exists.')
                    error_message = "Username already exists."
            else:
                error_message = "Invalid signup details."

    # Render login page
    response = render(request, 'game/login.html', {
        'login_form': login_form,
        'signup_form': signup_form,
        'show_signup': show_signup,
        'error_message': error_message,
        'success_message': success_message,
        'csrf_token': get_token(request)
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max_age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response.set_cookie('clueless_browser', browser_id, max_age=1800, httponly=True, samesite='Strict', path='/')
    response.delete_cookie('sessionid', path='/')
    # Clear any session-specific cookies on login page render
    for key in [k for k in request.COOKIES.keys() if k.startswith(('clueless_session_', 'clueless_browser_', 'clueless_user_', 'clueless_token_'))]:
        response.delete_cookie(key, path='/')
    if DEBUG and DEBUG_AUTH:
        print("[login_view] Outgoing response, Set-Cookie:")
        print(f"  clueless_browser: {browser_id}")
        print("  sessionid: deleted")
        print("  clueless_*: deleted")
    return response

def game_view(request, game_id):
    """
    Render the game page with strict session validation.
    Ensures session isolation by validating session-specific cookies and session token.
    Rejects requests with mismatched sessions or users with error pages to force logout.
    """
    session_key = request.session.session_key if request.session.session_key else 'unknown'
    sessionid = request.COOKIES.get('sessionid', 'None')
    clueless_session = request.COOKIES.get(f'clueless_session_{session_key}', 'None')
    clueless_browser = request.COOKIES.get(f'clueless_browser_{session_key}', 'None')
    clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')
    clueless_token = request.COOKIES.get(f'clueless_token_{session_key}', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')
    if DEBUG and DEBUG_AUTH:
        print("[game_view] Incoming request:")
        print(f"  sessionid: {sessionid}")
        print(f"  clueless_session_{session_key}: {clueless_session}")
        print(f"  clueless_browser_{session_key}: {clueless_browser}")
        print(f"  clueless_user_{session_key}: {clueless_user}")
        print(f"  clueless_token_{session_key}: {clueless_token}")
        print(f"  csrf_token: {csrf_token}")

    # Validate session-specific cookie
    if sessionid != request.session.session_key:
        if DEBUG and DEBUG_AUTH:
            print("[game_view] Session ID mismatch:")
            print(f"  Expected sessionid: {request.session.session_key}")
            print(f"  Got sessionid: {sessionid}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Invalid session ID. Please log in again."
        }, status=403)

    # Ensure session exists in database
    if not Session.objects.filter(session_key=request.session.session_key).exists():
        if DEBUG and DEBUG_AUTH:
            print("[game_view] Session not found:")
            print(f"  Session key: {request.session.session_key}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Session expired or invalid. Please log in again."
        }, status=403)

    # Validate expected_username from session
    expected_username = request.session.get('expected_username')
    if not expected_username:
        if DEBUG and DEBUG_AUTH:
            print("[game_view] Missing expected_username in session:")
            print(f"  Session key: {request.session.session_key}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Missing session data. Please log in again."
        }, status=403)

    # Validate clueless_user cookie against expected_username
    if clueless_user != 'None' and clueless_user != expected_username:
        if DEBUG and DEBUG_AUTH:
            print("[game_view] User cookie mismatch:")
            print(f"  Expected username: {expected_username}")
            print(f"  Got clueless_user: {clueless_user}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Invalid user cookie. Please log in again."
        }, status=403)

    # Check authentication
    if not request.user.is_authenticated:
        if DEBUG and DEBUG_AUTH:
            print("[game_view] Authentication failure:")
            print(f"  Game ID: {game_id}")
            print("  Reason: User not authenticated")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "You are not authenticated. Please log in."
        }, status=403)

    # Validate request.user.username against expected_username
    if request.user.username != expected_username:
        if DEBUG and DEBUG_AUTH:
            print("[game_view] Username mismatch:")
            print(f"  Expected username: {expected_username}")
            print(f"  Got username: {request.user.username}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Session mismatch detected. Please log in again."
        }, status=403)

    # Validate session token
    expected_token = request.session.get('session_token')
    signer = Signer()
    if clueless_token != 'None' and expected_token:
        try:
            unsigned_token = signer.unsign(clueless_token)
            token_username, token_session_key, token_browser_id, token_session_token = unsigned_token.split(':')
            if token_username != expected_username or token_session_key != request.session.session_key or \
               token_browser_id != request.session.get('browser_id'):
                if DEBUG and DEBUG_AUTH:
                    print("[game_view] Token validation failed:")
                    print(f"  Expected username: {expected_username}")
                    print(f"  Expected session_key: {request.session.session_key}")
                    print(f"  Expected browser_id: {request.session.get('browser_id')}")
                    print(f"  Got username: {token_username}")
                    print(f"  Got session_key: {token_session_key}")
                    print(f"  Got browser_id: {token_browser_id}")
                logout(request)
                request.session.flush()
                return render(request, 'game/error.html', {
                    'error_message': "Invalid session token. Please log in again."
                }, status=403)
        except (BadSignature, ValueError):
            if DEBUG and DEBUG_AUTH:
                print("[game_view] Invalid token signature:")
                print(f"  Token: {clueless_token}")
            logout(request)
            request.session.flush()
            return render(request, 'game/error.html', {
                'error_message': "Invalid session token signature. Please log in again."
            }, status=403)

    # Validate browser ID
    expected_browser_id = request.session.get('browser_id')
    if not expected_browser_id:
        if DEBUG and DEBUG_AUTH:
            print("[game_view] Missing browser ID:")
            print(f"  Expected browser_id: {expected_browser_id}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Missing browser ID in session. Please log in again."
        }, status=403)
    if clueless_browser != expected_browser_id:
        if DEBUG and DEBUG_AUTH:
            print("[game_view] Browser cookie mismatch:")
            print(f"  Expected browser_id: {expected_browser_id}")
            print(f"  Got clueless_browser: {clueless_browser}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Invalid browser cookie. Please log in again."
        }, status=403)

    # Validate session cookie
    expected_session_id = request.session.get('expected_session_id')
    if clueless_session != 'None' and expected_session_id and clueless_session != expected_session_id:
        if DEBUG and DEBUG_AUTH:
            print("[game_view] Session cookie mismatch:")
            print(f"  Expected session_id: {expected_session_id}")
            print(f"  Got clueless_session: {clueless_session}")
        logout(request)
        request.session.flush()
        return render(request, 'game/error.html', {
            'error_message': "Invalid session cookie. Please log in again."
        }, status=403)

    # Validate game existence
    try:
        game = Game.objects.get(id=game_id)
    except Game.DoesNotExist:
        if DEBUG and DEBUG_AUTH:
            print("[game_view] Game not found:")
            print(f"  Game ID: {game_id}")
        return render(request, 'game/error.html', {
            'error_message': "Game not found."
        }, status=404)

    # Redirect if game hasn't started
    if not game.begun:
        return redirect('start_game', game_id=game_id)

    # Fetch and validate player
    game_state = get_game_state(game)
    try:
        player = Player.objects.get(game=game, username=request.user.username)
        if not player.is_active:
            if DEBUG and DEBUG_AUTH:
                print("[game_view] Reactivating player:")
                print(f"  Username: {request.user.username}")
                print(f"  Game ID: {game_id}")
            player.is_active = True
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
        if request.user.username in game.players_list:
            if DEBUG and DEBUG_AUTH:
                print("[game_view] Reassigning player:")
                print(f"  Username: {request.user.username}")
                print(f"  Game ID: {game_id}")
            assign_random_character(game, request.user)
            try:
                player = Player.objects.get(game=game, username=request.user.username)
            except Player.DoesNotExist:
                if DEBUG and DEBUG_AUTH:
                    print("[game_view] Failed to reassign player:")
                    print(f"  Username: {request.user.username}")
                    print(f"  Game ID: {game_id}")
                return render(request, 'game/error.html', {
                    'error_message': "Unable to assign a player. The game may be full or an error occurred."
                }, status=403)
        else:
            if DEBUG and DEBUG_AUTH:
                print("[game_view] User not in game:")
                print(f"  Username: {request.user.username}")
                print(f"  Game ID: {game_id}")
            return render(request, 'game/error.html', {
                'error_message': "You are not a player in this game. Please join the game."
            }, status=403)

    # Log successful rendering
    if DEBUG and DEBUG_AUTH:
        print("[game_view] Rendering game view:")
        print(f"  Username: {request.user.username}")
        print(f"  Session: {request.session.session_key}")
        print(f"  Expected username: {expected_username}")
        print(f"  Expected session_id: {expected_session_id}")
        print(f"  Browser ID: {expected_browser_id}")
        print(f"  Character: {player.character}")
        print(f"  Game ID: {game_id}")

    # Render game page
    response = render(request, 'game/game.html', {
        'game_id': game_id,
        'players': game_state['players'],
        'username': request.user.username,
        'character': player.character
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max_age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    # Set session-specific cookies
    response.set_cookie('sessionid', request.session.session_key, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_session_{request.session.session_key}', request.session.session_key, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_browser_{request.session.session_key}', expected_browser_id, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_user_{request.session.session_key}', request.user.username, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_token_{request.session.session_key}', expected_token, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    if DEBUG and DEBUG_AUTH:
        print("[game_view] Outgoing response, Set-Cookie:")
        print(f"  sessionid: {request.session.session_key}")
        print(f"  clueless_session_{request.session.session_key}: {request.session.session_key}")
        print(f"  clueless_browser_{request.session.session_key}: {expected_browser_id}")
        print(f"  clueless_user_{request.session.session_key}: {request.user.username}")
        print(f"  clueless_token_{request.session.session_key}: {expected_token}")

    return response

def start_game(request, game_id):
    """
    Render the start game page.
    Allows the first player to initiate the game.
    Validates session-specific cookies to ensure authorized access.
    """
    session_key = request.session.session_key if request.session.session_key else 'unknown'
    sessionid = request.COOKIES.get('sessionid', 'None')
    clueless_session = request.COOKIES.get(f'clueless_session_{session_key}', 'None')
    clueless_browser = request.COOKIES.get(f'clueless_browser_{session_key}', 'None')
    clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')
    clueless_token = request.COOKIES.get(f'clueless_token_{session_key}', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')
    if DEBUG and DEBUG_AUTH:
        print("[start_game] Incoming request:")
        print(f"  sessionid: {sessionid}")
        print(f"  clueless_session_{session_key}: {clueless_session}")
        print(f"  clueless_browser_{session_key}: {clueless_browser}")
        print(f"  clueless_user_{session_key}: {clueless_user}")
        print(f"  clueless_token_{session_key}: {clueless_token}")
        print(f"  csrf_token: {csrf_token}")

    # Check authentication
    if not request.user.is_authenticated:
        if DEBUG and DEBUG_AUTH:
            print("[start_game] Authentication failure:")
            print(f"  Game ID: {game_id}")
            print("  Reason: User not authenticated")
        return render(request, 'game/error.html', {
            'error_message': "You are not authenticated. Please log in."
        }, status=403)

    # Validate game existence
    try:
        game = Game.objects.get(id=game_id)
    except Game.DoesNotExist:
        if DEBUG and DEBUG_AUTH:
            print("[start_game] Game not found:")
            print(f"  Game ID: {game_id}")
        return render(request, 'game/error.html', {
            'error_message': "Game not found."
        }, status=404)

    # Redirect if game has started
    if game.begun:
        return redirect('game_view', game_id=game_id)

    # Determine if user is the first player
    is_first_user = game.players_list[0] == request.user.username if game.players_list else False

    # Render start game page
    response = render(request, 'game/start_game.html', {
        'game_id': game_id,
        'is_first_user': is_first_user,
        'players_list': game.players_list,
        'player_count': len(game.players_list)
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max_age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response.delete_cookie('sessionid', path='/')
    # Clear any session-specific cookies that don't match the current session
    for key in [k for k in request.COOKIES.keys() if k.startswith(('clueless_session_', 'clueless_browser_', 'clueless_user_', 'clueless_token_')) and not k.endswith(session_key)]:
        response.delete_cookie(key, path='/')
    if DEBUG and DEBUG_AUTH:
        print("[start_game] Outgoing response:")
        print("  Set-Cookie: None")
        print("  sessionid: deleted")
        print("  stale clueless_*: deleted")

    return response

def logout_view(request):
    """
    Handle user logout.
    Clears session data, deactivates the player, and removes all cookies.
    """
    session_key = request.session.session_key if request.session.session_key else 'unknown'
    sessionid = request.COOKIES.get('sessionid', 'None')
    clueless_session = request.COOKIES.get(f'clueless_session_{session_key}', 'None')
    clueless_browser = request.COOKIES.get(f'clueless_browser_{session_key}', 'None')
    clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')
    clueless_token = request.COOKIES.get(f'clueless_token_{session_key}', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')
    if DEBUG and DEBUG_AUTH:
        print("[logout_view] Incoming request:")
        print(f"  sessionid: {sessionid}")
        print(f"  clueless_session_{session_key}: {clueless_session}")
        print(f"  clueless_browser_{session_key}: {clueless_browser}")
        print(f"  clueless_user_{session_key}: {clueless_user}")
        print(f"  clueless_token_{session_key}: {clueless_token}")
        print(f"  csrf_token: {csrf_token}")

    # Deactivate player if authenticated
    if request.user.is_authenticated:
        try:
            game = Game.objects.get(id=1)
            try:
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
                if DEBUG and DEBUG_AUTH:
                    print("[logout_view] Player deactivated:")
                    print(f"  Username: {request.user.username}")
                    print(f"  Game ID: 1")
            except Player.DoesNotExist:
                if DEBUG and DEBUG_AUTH:
                    print("[logout_view] Player not found:")
                    print(f"  Username: {request.user.username}")
                    print(f"  Game ID: 1")
        except Game.DoesNotExist:
            if DEBUG and DEBUG_AUTH:
                print("[logout_view] Game not found:")
                print("  Game ID: 1")

    # Clear session and cookies
    logout(request)
    request.session.flush()

    response = redirect('login')
    for key in list(request.COOKIES.keys()):
        response.delete_cookie(key, path='/')
    response.delete_cookie('sessionid', path='/')
    response.delete_cookie('clueless_session', path='/')
    response.delete_cookie('clueless_browser', path='/')
    response.delete_cookie('clueless_user', path='/')
    response.delete_cookie('clueless_token', path='/')
    response.delete_cookie('csrftoken', path='/')
    if DEBUG and DEBUG_AUTH:
        print("[logout_view] Outgoing response, Set-Cookie:")
        print("  sessionid: deleted")
        print("  clueless_session: deleted")
        print("  clueless_browser: deleted")
        print("  clueless_user: deleted")
        print("  clueless_token: deleted")
        print("  csrftoken: deleted")

    return response

def assign_random_character(game, user):
    """
    Assign a random character to the user or reactivate an existing one.
    Ensures no duplicate characters and broadcasts updated game state.
    """
    try:
        player = Player.objects.get(game=game, username=user.username)
        if not player.is_active:
            player.is_active = True
            player.save()
            if DEBUG and DEBUG_ASSIGN_RANDOM_CHARACTER:
                print("[assign_random_character] Reactivated player:")
                print(f"  Username: {user.username}")
                print(f"  Character: {player.character}")
    except Player.DoesNotExist:
        with transaction.atomic():
            taken_characters = game.players.values_list('character', flat=True)
            available_characters = [char for char in SUSPECTS if char not in taken_characters]
            if not available_characters:
                raise ValueError("No available characters left in this game.")

            character = random.choice(available_characters)
            if game.players.filter(character=character).exists():
                raise ValueError(f"Character {character} already assigned to a player!")
            player = Player.objects.create(
                game=game,
                username=user.username,
                character=character,
                location=STARTING_LOCATIONS[character],
                is_active=True,
                turn=False,
                hand=[],
                moved=False,
                accused=False,
                suggested=False
            )

            if user.username not in game.players_list:
                game.players_list.append(user.username)
                game.save()

            if DEBUG and DEBUG_ASSIGN_RANDOM_CHARACTER:
                print("[assign_random_character] Assigned new player:")
                print(f"  Username: {user.username}")
                print(f"  Character: {character}")

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
    """
    Retrieve game state for WebSocket updates and rendering.
    Includes all players, game status, and game constants.
    """
    fields = [f.name for f in Player._meta.fields]
    players = list(game.players.values(*fields))
    return {
        'case_file': game.case_file if not game.is_active else None,
        'game_is_active': game.is_active,
        'players': players,
        'rooms': ROOMS,
        'hallways': HALLWAYS,
        'weapons': WEAPONS
    }