"""
Views for the Clue-Less game, handling user authentication, game rendering, and logout.

This module defines view functions for user login/signup, game page rendering, lobby
management, and logout. It manages session creation, cookie handling, and player state,
integrating with WebSocket communication via Channels for real-time updates. Key
features include session isolation to prevent overwrites, authentication checks to
avoid unauthorized access, and game state broadcasting.

For more information, see:
- https://docs.djangoproject.com/en/5.1/topics/http/views/
- https://docs.djangoproject.com/en/5.1/topics/auth/
- https://docs.djangoproject.com/en/5.1/topics/http/sessions/
- https://channels.readthedocs.io/en/stable/topics/consumers.html
"""

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

class SignupForm(forms.Form):
    """Form for user signup with username and password fields."""
    username = forms.CharField(max_length=150, required=True, help_text="Username (max 150 characters)")
    password = forms.CharField(widget=forms.PasswordInput, required=True, help_text="Password")

def login_view(request):
    """
    Handle user login and signup, creating sessions and setting cookies.

    Manages login/signup forms, validates credentials, creates new sessions, and sets
    session-specific cookies to ensure isolation. Clears existing cookies to prevent
    session overwrites, especially in private browsing modes (e.g., Safari). Redirects
    to the game page on successful login or renders the login page with errors.

    - **Authentication**: Uses Django's AuthenticationForm to validate username/password,
      calling login() to authenticate the user and attach them to the session.
      Checks game capacity (6 players max) to prevent overjoining, ensuring only
      authorized users join the game.
    - **Session Handling**: Flushes existing sessions and creates a new one within a
      transaction to ensure atomicity. Stores expected_username, expected_session_id,
      browser_id, and a signed session_token in the session to support
      SessionValidationMiddleware's validation, preventing session overwrites.
    - **Cookie Handling**: Clears all cookies before login to eliminate stale or foreign
      sessions, addressing session overwrite issues in private browsing. Sets new
      sessionid and clueless_* cookies (session, browser, user, token) with a 30-minute
      expiry, HttpOnly, and SameSite=Strict for security. Deletes sessionid on GET
      requests to ensure a clean state when rendering the login page.
    - **Error Handling**: Validates session existence in the database to catch save
      failures, returning an error page (status 500) if the session cannot be saved.
      Logs cookie details and session state for debugging overwrite issues.
    - **Security**: Uses CSRF tokens for POST requests and signs session_token to
      prevent tampering, aligning with Django's security practices.
    """
    # Initialize login and signup forms
    login_form = AuthenticationForm()
    signup_form = SignupForm()
    show_signup = 'signup' in request.GET or 'signup' in request.POST
    error_message = None
    success_message = None

    # Get or create Game instance (ID=1) with default empty case_file and players_list
    game, _ = Game.objects.get_or_create(id=1, defaults={'case_file': {}, 'players_list': []})
    all_players = game.players_list

    # Retrieve cookies for debugging and validation
    sessionid = request.COOKIES.get('sessionid', 'None')
    session_key = request.session.session_key if request.session.session_key else 'unknown'
    clueless_session = request.COOKIES.get(f'clueless_session_{session_key}', 'None')
    clueless_browser = request.COOKIES.get(f'clueless_browser_{session_key}', 'None')
    clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')
    clueless_token = request.COOKIES.get(f'clueless_token_{session_key}', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')

    # Log incoming cookies for debugging session issues
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
    signer = Signer()  # For signing session_token
    session_token = str(uuid.uuid4())  # Unique token for session validation

    if request.method == 'POST':
        if 'login' in request.POST:
            # Process login form submission
            login_form = AuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                # Authenticate user and retrieve User object
                user = login_form.get_user()
                # Check if game is full (max 6 players)
                if len(game.players_list) >= 6 and user.username not in game.players_list:
                    error_message = "The game is already full with 6 players."
                else:
                    # Prepare redirect response to game page
                    response = HttpResponse(status=302)
                    response['Location'] = f'/game/{game.id}/'

                    # Clear all existing cookies to prevent session overwrites
                    for key in list(request.COOKIES.keys()):
                        response.delete_cookie(key, path='/')

                    # Create new session atomically to ensure consistency
                    with transaction.atomic():
                        # Flush any existing session to start fresh
                        request.session.flush()
                        # Create a new session
                        request.session.create()
                        # Authenticate and attach user to session
                        login(request, user)
                        # Store validation data in session for SessionValidationMiddleware
                        request.session['expected_username'] = user.username
                        request.session['expected_session_id'] = request.session.session_key
                        request.session['browser_id'] = browser_id
                        # Sign session token to prevent tampering
                        request.session['session_token'] = signer.sign(
                            f"{user.username}:{request.session.session_key}:{browser_id}:{session_token}")
                        request.session.modified = True
                        request.session.save()

                        # Verify session was saved to database
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

                    # Assign or reactivate player character
                    assign_random_character(game, user)

                    # Set success message for user feedback
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

                    # Set session-specific cookies with 30-minute expiry
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

                    # Log outgoing cookies for debugging
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
            # Process signup form submission
            signup_form = SignupForm(request.POST)
            if signup_form.is_valid():
                username = signup_form.cleaned_data['username']
                password = signup_form.cleaned_data['password']
                if not User.objects.filter(username=username).exists():
                    # Create new user (no session/cookie handling here)
                    User.objects.create_user(username=username, password=password)
                    success_message = f"Signup successful for {username}! Please log in."
                    show_signup = False
                    signup_form = SignupForm()
                else:
                    signup_form.add_error('username', 'Username already exists.')
                    error_message = "Username already exists."
            else:
                error_message = "Invalid signup details."

    # Render login page for GET requests or failed POST attempts
    response = render(request, 'game/login.html', {
        'login_form': login_form,
        'signup_form': signup_form,
        'show_signup': show_signup,
        'error_message': error_message,
        'success_message': success_message,
        'csrf_token': get_token(request)
    })

    # Set cache headers to prevent caching sensitive login pages
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max_age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    # Set clueless_browser cookie for tracking; clear session-related cookies
    response.set_cookie('clueless_browser', browser_id, max_age=1800, httponly=True, samesite='Strict', path='/')
    response.delete_cookie('sessionid', path='/')
    for key in [k for k in request.COOKIES.keys() if k.startswith(('clueless_session_', 'clueless_browser_', 'clueless_user_', 'clueless_token_'))]:
        response.delete_cookie(key, path='/')

    # Log outgoing cookies for debugging
    if DEBUG and DEBUG_AUTH:
        print("[login_view] Outgoing response, Set-Cookie:")
        print(f"  clueless_browser: {browser_id}")
        print("  sessionid: deleted")
        print("  clueless_*: deleted")
    return response

def game_view(request, game_id):
    """
    Render the game page, validating authentication and player state.

    Relies on SessionValidationMiddleware for session isolation, checks user
    authentication, and ensures the player is part of the game. Reactivates or
    reassigns players as needed, broadcasting updates via WebSocket.

    - **Authentication**: Verifies request.user.is_authenticated to ensure only
      authenticated users access the game page, returning an error page (status 403)
      if unauthenticated. Relies on AuthenticationMiddleware to set request.user,
      fixed by middleware reordering to avoid AttributeError.
    - **Session Handling**: Retrieves session_key for logging; relies on
      SessionValidationMiddleware to validate session integrity before reaching this
      view, ensuring no foreign sessions are trusted.
    - **Cookie Handling**: Logs sessionid and clueless_* cookies for debugging but
      does not validate them here (handled by middleware). Sets sessionid and
      clueless_* cookies on response to maintain session state, with 30-minute expiry,
      HttpOnly, and SameSite=Strict for security. Cache headers prevent storing
      sensitive game data.
    """
    # Retrieve session and cookie details for debugging
    session_key = request.session.session_key if request.session.session_key else 'unknown'
    sessionid = request.COOKIES.get('sessionid', 'None')
    clueless_session = request.COOKIES.get(f'clueless_session_{session_key}', 'None')
    clueless_browser = request.COOKIES.get(f'clueless_browser_{session_key}', 'None')
    clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')
    clueless_token = request.COOKIES.get(f'clueless_token_{session_key}', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')

    # Log incoming cookies for debugging
    if DEBUG and DEBUG_AUTH:
        print("[game_view] Incoming request:")
        print(f"  sessionid: {sessionid}")
        print(f"  clueless_session_{session_key}: {clueless_session}")
        print(f"  clueless_browser_{session_key}: {clueless_browser}")
        print(f"  clueless_user_{session_key}: {clueless_user}")
        print(f"  clueless_token_{session_key}: {clueless_token}")
        print(f"  csrf_token: {csrf_token}")

    # Check if user is authenticated
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

    # Retrieve game instance
    try:
        game = Game.objects.get(id=game_id)
    except Game.DoesNotExist:
        if DEBUG and DEBUG_AUTH:
            print("[game_view] Game not found:")
            print(f"  Game ID: {game_id}")
        return render(request, 'game/error.html', {
            'error_message': "Game not found."
        }, status=404)

    # Redirect to start_game if game hasn't begun
    if not game.begun:
        return redirect('start_game', game_id=game_id)

    # Get game state for rendering and updates
    game_state = get_game_state(game)

    # Manage player state
    try:
        player = Player.objects.get(game=game, username=request.user.username)
        if not player.is_active:
            if DEBUG and DEBUG_AUTH:
                print("[game_view] Reactivating player:")
                print(f"  Username: {request.user.username}")
                print(f"  Game ID: {game_id}")
            player.is_active = True
            player.save()
            # Broadcast updated game state via WebSocket
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

    # Log rendering details for debugging
    if DEBUG and DEBUG_AUTH:
        print("[game_view] Rendering game view:")
        print(f"  Username: {request.user.username}")
        print(f"  Session: {request.session.session_key}")
        print(f"  Character: {player.character}")
        print(f"  Game ID: {game_id}")

    # Render game page
    response = render(request, 'game/game.html', {
        'game_id': game_id,
        'players': game_state['players'],
        'username': request.user.username,
        'character': player.character
    })

    # Set cache headers to prevent caching sensitive game data
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max_age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    # Set session cookies to maintain state
    expected_username = request.session.get('expected_username', '')
    expected_browser_id = request.session.get('browser_id', '')
    expected_token = request.session.get('session_token', '')
    response.set_cookie('sessionid', request.session.session_key, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_session_{request.session.session_key}', request.session.session_key, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_browser_{request.session.session_key}', expected_browser_id, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_user_{request.session.session_key}', expected_username, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_token_{request.session.session_key}', expected_token, max_age=1800,
                       httponly=True, samesite='Strict', path='/')

    # Log outgoing cookies for debugging
    if DEBUG and DEBUG_AUTH:
        print("[game_view] Outgoing response, Set-Cookie:")
        print(f"  sessionid: {request.session.session_key}")
        print(f"  clueless_session_{request.session.session_key}: {request.session.session_key}")
        print(f"  clueless_browser_{request.session.session_key}: {expected_browser_id}")
        print(f"  clueless_user_{request.session.session_key}: {expected_username}")
        print(f"  clueless_token_{request.session.session_key}: {expected_token}")

    return response

def start_game(request, game_id):
    """
    Render the start game page, allowing the host to initiate the game.

    Validates authentication and game state, preserving session cookies to prevent
    reload errors. Supports lobby functionality with dynamic player updates.

    - **Authentication**: Checks request.user.is_authenticated to ensure only
      authenticated users access the lobby, returning an error page (status 403) if
      unauthenticated. Relies on AuthenticationMiddleware, fixed by middleware
      reordering to avoid AttributeError.
    - **Session Handling**: Retrieves session_key for logging; relies on
      SessionValidationMiddleware for validation. Preserves session state to allow
      reloads without errors, addressing prior lobby reload issues.
    - **Cookie Handling**: Logs sessionid and clueless_* cookies for debugging.
      Preserves sessionid and clueless_* cookies on response (unlike initial
      implementation that deleted them), ensuring session continuity on reloads.
      Sets cookies with 30-minute expiry, HttpOnly, and SameSite=Strict for security.
      Cache headers prevent storing sensitive lobby data.
    """
    # Retrieve session and cookie details for debugging
    session_key = request.session.session_key if request.session.session_key else 'unknown'
    sessionid = request.COOKIES.get('sessionid', 'None')
    clueless_session = request.COOKIES.get(f'clueless_session_{session_key}', 'None')
    clueless_browser = request.COOKIES.get(f'clueless_browser_{session_key}', 'None')
    clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')
    clueless_token = request.COOKIES.get(f'clueless_token_{session_key}', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')

    # Log incoming cookies for debugging
    if DEBUG and DEBUG_AUTH:
        print("[start_game] Incoming request:")
        print(f"  sessionid: {sessionid}")
        print(f"  clueless_session_{session_key}: {clueless_session}")
        print(f"  clueless_browser_{session_key}: {clueless_browser}")
        print(f"  clueless_user_{session_key}: {clueless_user}")
        print(f"  clueless_token_{session_key}: {clueless_token}")
        print(f"  csrf_token: {csrf_token}")

    # Check if user is authenticated
    if not request.user.is_authenticated:
        if DEBUG and DEBUG_AUTH:
            print("[start_game] Authentication failure:")
            print(f"  Game ID: {game_id}")
            print("  Reason: User not authenticated")
        return render(request, 'game/error.html', {
            'error_message': "You are not authenticated. Please log in."
        }, status=403)

    # Retrieve game instance
    try:
        game = Game.objects.get(id=game_id)
    except Game.DoesNotExist:
        if DEBUG and DEBUG_AUTH:
            print("[start_game] Game not found:")
            print(f"  Game ID: {game_id}")
        return render(request, 'game/error.html', {
            'error_message': "Game not found."
        }, status=404)

    # Redirect to game_view if game has begun
    if game.begun:
        return redirect('game_view', game_id=game_id)

    # Determine if user is the host (first player in players_list)
    is_first_user = game.players_list[0] == request.user.username if game.players_list else False

    # Render start game page
    response = render(request, 'game/start_game.html', {
        'game_id': game_id,
        'is_first_user': is_first_user,
        'players_list': game.players_list,
        'player_count': len(game.players_list)
    })

    # Set cache headers to prevent caching sensitive lobby data
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max_age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    # Preserve session cookies to maintain state on reload
    expected_username = request.session.get('expected_username', '')
    expected_browser_id = request.session.get('browser_id', '')
    expected_token = request.session.get('session_token', '')
    response.set_cookie('sessionid', request.session.session_key, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_session_{request.session.session_key}', request.session.session_key, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_browser_{request.session.session_key}', expected_browser_id, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_user_{request.session.session_key}', expected_username, max_age=1800,
                       httponly=True, samesite='Strict', path='/')
    response.set_cookie(f'clueless_token_{request.session.session_key}', expected_token, max_age=1800,
                       httponly=True, samesite='Strict', path='/')

    # Log outgoing cookies for debugging
    if DEBUG and DEBUG_AUTH:
        print("[start_game] Outgoing response, Set-Cookie:")
        print(f"  sessionid: {request.session.session_key}")
        print(f"  clueless_session_{request.session.session_key}: {request.session.session_key}")
        print(f"  clueless_browser_{request.session.session_key}: {expected_browser_id}")
        print(f"  clueless_user_{request.session.session_key}: {expected_username}")
        print(f"  clueless_token_{request.session.session_key}: {expected_token}")

    return response

def logout_view(request):
    """
    Handle user logout, clearing sessions and deactivating players.

    Clears session data, deactivates the player in the game, and removes all cookies,
    ensuring a clean state for the next login.

    - **Authentication**: Checks request.user.is_authenticated to identify the user
      for deactivation, proceeding with logout regardless to clear any session state.
      Relies on AuthenticationMiddleware for request.user, fixed by middleware
      reordering to avoid AttributeError.
    - **Session Handling**: Flushes the session to remove all data, ensuring no stale
      session persists. Broadcasts game state updates via WebSocket if the player is
      deactivated, maintaining game consistency.
    - **Cookie Handling**: Retrieves and logs sessionid and clueless_* cookies for
      debugging. Deletes all cookies (sessionid, clueless_*, csrftoken) on response to
      prevent reuse, addressing session overwrite risks. Uses path='/' to ensure
      complete removal across all paths.
    """
    # Retrieve session and cookie details for debugging
    session_key = request.session.session_key if request.session.session_key else 'unknown'
    sessionid = request.COOKIES.get('sessionid', 'None')
    clueless_session = request.COOKIES.get(f'clueless_session_{session_key}', 'None')
    clueless_browser = request.COOKIES.get(f'clueless_browser_{session_key}', 'None')
    clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')
    clueless_token = request.COOKIES.get(f'clueless_token_{session_key}', 'None')
    csrf_token = request.COOKIES.get('csrftoken', 'None')

    # Log incoming cookies for debugging
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
                # Broadcast updated game state via WebSocket
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

    # Clear session and log out user
    logout(request)
    request.session.flush()

    # Prepare redirect to login page
    response = redirect('login')

    # Delete all cookies to ensure clean state
    for key in list(request.COOKIES.keys()):
        response.delete_cookie(key, path='/')
    response.delete_cookie('sessionid', path='/')
    response.delete_cookie('clueless_session', path='/')
    response.delete_cookie('clueless_browser', path='/')
    response.delete_cookie('clueless_user', path='/')
    response.delete_cookie('clueless_token', path='/')
    response.delete_cookie('csrftoken', path='/')

    # Log outgoing cookies for debugging
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
    """Assign or reactivate a random character for a user, broadcasting updates."""
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

    # Broadcast updated game state via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"game_{game.id}",
        {
            'type': 'game_update',
            'game_state': get_game_state(game)
        }
    )

def get_game_state(game):
    """Retrieve game state for WebSocket updates and rendering."""
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