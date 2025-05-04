from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import logout
from django.shortcuts import render

# Debug flag for logging; disable in production
DEBUG = True

class SessionValidationMiddleware:
    """
    Middleware to validate session cookies after AuthenticationMiddleware.
    Checks clueless_user_<session_key> against expected_username to reject foreign sessions.
    Skips validation for /login/ to avoid accessing request.user prematurely.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session_key = request.COOKIES.get('sessionid')
        clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')

        if DEBUG:
            print("[SessionValidationMiddleware] Cookie details:")
            print(f"  Path: {request.path}")
            print(f"  sessionid: {session_key or 'None'}")
            print(f"  clueless_user_{session_key or 'unknown'}: {clueless_user}")

        # Skip validation for /login/ to avoid AttributeError on request.user
        if request.path.startswith('/login/'):
            return self.get_response(request)

        # Handle /start_game/ with authentication check
        if request.path.startswith('/start_game/'):
            if not request.user.is_authenticated:
                if DEBUG:
                    print("[SessionValidationMiddleware] Authentication failure for /start_game/:")
                    print(f"  Session key: {session_key}")
                return render(request, 'game/error.html', {
                    'error_message': "You are not authenticated. Please log in."
                }, status=403)
            return self.get_response(request)

        # Validate session for other paths
        if session_key:
            try:
                request.session = SessionStore(session_key=session_key)
                request.session.accessed = True
                expected_username = request.session.get('expected_username')

                if expected_username and clueless_user != 'None' and clueless_user != expected_username:
                    if DEBUG:
                        print("[SessionValidationMiddleware] Session user mismatch:")
                        print(f"  Session key: {session_key}")
                        print(f"  Expected username: {expected_username}")
                        print(f"  Got clueless_user: {clueless_user}")
                    logout(request)
                    request.session.flush()
                    return render(request, 'game/error.html', {
                        'error_message': "Invalid user session. Please log in again."
                    }, status=403)

                if DEBUG:
                    print("[SessionValidationMiddleware] Session loaded:")
                    print(f"  Session key: {session_key}")
            except Exception as e:
                if DEBUG:
                    print("[SessionValidationMiddleware] Failed to load session:")
                    print(f"  Session key: {session_key}")
                    print(f"  Error: {str(e)}")
                request.session = SessionStore()
        else:
            request.session = SessionStore()
            if DEBUG:
                print("[SessionValidationMiddleware] No session key found, using new session")

        return self.get_response(request)