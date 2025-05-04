from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import logout
from django.shortcuts import render

# Debug flag for logging; disable in production
DEBUG = True

class SessionValidationMiddleware:
    """
    Middleware to validate session cookies before AuthenticationMiddleware.
    Checks clueless_user_<session_key> against expected_username to reject foreign sessions.
    Prevents session overwrites in private browsing modes by forcing logout on mismatch.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get session key from sessionid cookie
        session_key = request.COOKIES.get('sessionid')
        clueless_user = request.COOKIES.get(f'clueless_user_{session_key}', 'None')

        # Log cookies for debugging
        if DEBUG:
            print("[SessionValidationMiddleware] Cookie details:")
            print(f"  Path: {request.path}")
            print(f"  sessionid: {session_key or 'None'}")
            print(f"  clueless_user_{session_key or 'unknown'}: {clueless_user}")

        # Skip validation for non-game paths
        if not request.path.startswith(('/game/', '/logout/', '/start_game/', '/ws/game/')):
            return self.get_response(request)

        # Load session
        if session_key:
            try:
                request.session = SessionStore(session_key=session_key)
                request.session.accessed = True
                expected_username = request.session.get('expected_username')

                # Validate clueless_user against expected_username
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