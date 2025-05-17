"""
Custom middleware for the Clue-Less game to validate session cookies.

This module defines SessionValidationMiddleware, which ensures session integrity by
validating the clueless_user_<session_key> cookie against the expected_username in
the session. It prevents session overwrites in private browsing modes (e.g., Safari)
and skips validation for /login/ to avoid AttributeError on request.user. The
middleware is critical for maintaining user state in a multiplayer WebSocket-based
game using Django and Channels.

For more information, see:
- https://docs.djangoproject.com/en/5.1/topics/http/middleware/
- https://docs.djangoproject.com/en/5.1/topics/http/sessions/
"""

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import logout
from django.shortcuts import render

# Debug flag for logging; disable in production to reduce verbosity
# When True, logs detailed session and cookie information for debugging
# Set to False in production to improve performance and security
DEBUG = False

class SessionValidationMiddleware:
    """
    Middleware to validate session cookies after AuthenticationMiddleware.

    Checks the clueless_user_<session_key> cookie against the expected_username
    stored in the session to reject foreign sessions, preventing session overwrites
    in private browsing modes (e.g., Safari). Skips validation for /login/ to avoid
    accessing request.user before AuthenticationMiddleware sets it, fixing
    AttributeError: 'ASGIRequest' object has no attribute 'user'. For /start_game/,
    ensures authentication to prevent unauthorized access while allowing reloads
    without errors. Logs session and cookie details for debugging when DEBUG is True.
    """
    def __init__(self, get_response):
        """
        Initialize the middleware with the get_response callable.

        Args:
            get_response (callable): The next middleware or view in the request/response chain.
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Process each request to validate session cookies.

        Retrieves the sessionid cookie and corresponding clueless_user_<session_key>
        cookie, validates them against the session's expected_username, and rejects
        mismatched sessions with an error page. Skips validation for /login/ to
        prevent AttributeError and checks authentication for /start_game/ to ensure
        secure access. Logs cookie details and session validation status for debugging.

        Args:
            request (ASGIRequest): The incoming request object.

        Returns:
            HttpResponse: The response from the next middleware/view, or an error page
                          if validation fails or authentication is required.
        """
        # Retrieve the sessionid cookie to identify the session
        session_key = request.COOKIES.get('sessionid')

        # Get the clueless_user_<session_key> cookie for validation
        # Defaults to 'None' if the cookie is missing
        clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')

        # Log cookie details for debugging when DEBUG is enabled
        # Helps diagnose session overwrite or validation issues
        if DEBUG:
            print("[SessionValidationMiddleware] Cookie details:")
            print(f"  Path: {request.path}")
            print(f"  sessionid: {session_key or 'None'}")
            print(f"  clueless_user_{session_key or 'unknown'}: {clueless_user}")

        # Skip all validation for /login/ to avoid accessing request.user
        # Prevents AttributeError: 'ASGIRequest' object has no attribute 'user'
        # before AuthenticationMiddleware sets it
        if request.path.startswith('/login/'):
            return self.get_response(request)

        # Handle /start_game/ with authentication check to prevent unauthorized access
        # Allows reloads without triggering session validation errors, preserving
        # lobby functionality (dynamic player updates, start button)
        if request.path.startswith('/start_game/'):
            # Check if the user is authenticated (set by AuthenticationMiddleware)
            if not request.user.is_authenticated:
                if DEBUG:
                    print("[SessionValidationMiddleware] Authentication failure for /start_game/:")
                    print(f"  Session key: {session_key}")
                # Return an error page if unauthenticated, requiring login
                return render(request, 'game/error.html', {
                    'error_message': "You are not authenticated. Please log in."
                }, status=403)
            return self.get_response(request)

        # Validate session for all other paths (e.g., /game/, /logout/)
        if session_key:
            try:
                # Load the session from the database using the session_key
                request.session = SessionStore(session_key=session_key)
                request.session.accessed = True  # Mark session as accessed
                # Retrieve the expected_username stored during login
                expected_username = request.session.get('expected_username')

                # Check for session overwrite by comparing clueless_user cookie
                # with expected_username
                if expected_username and clueless_user != 'None' and clueless_user != expected_username:
                    if DEBUG:
                        print("[SessionValidationMiddleware] Session user mismatch:")
                        print(f"  Session key: {session_key}")
                        print(f"  Expected username: {expected_username}")
                        print(f"  Got clueless_user: {clueless_user}")
                    # Log out the user and flush the session to clear invalid state
                    logout(request)
                    request.session.flush()
                    # Return an error page to prompt re-login
                    return render(request, 'game/error.html', {
                        'error_message': "Invalid user session. Please log in again."
                    }, status=403)

                # Log successful session loading for debugging
                if DEBUG:
                    print("[SessionValidationMiddleware] Session loaded:")
                    print(f"  Session key: {session_key}")

            except Exception as e:
                # Handle session loading errors (e.g., invalid session_key)
                if DEBUG:
                    print("[SessionValidationMiddleware] Failed to load session:")
                    print(f"  Session key: {session_key}")
                    print(f"  Error: {str(e)}")
                # Create a new empty session to prevent further errors
                request.session = SessionStore()
        else:
            # No sessionid cookie found; create a new empty session
            request.session = SessionStore()
            if DEBUG:
                print("[SessionValidationMiddleware] No session key found, using new session")

        # Pass the request to the next middleware or view
        return self.get_response(request)