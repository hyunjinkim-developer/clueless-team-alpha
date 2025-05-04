# Django imports for session middleware and settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import logout

# Debug flag for logging; disable in production
DEBUG = True  # Enables/disables all debug logging


class CustomSessionMiddleware(SessionMiddleware):
    """
    Custom session middleware to enforce session isolation for game views.
    Uses session-specific cookies (sessionid_<session_key>) for game-related requests,
    explicitly rejecting the generic 'sessionid' cookie to prevent session overwrites.
    Validates all clueless_user_* cookies against session's expected_username to prevent session hijacking.
    Clears stale session-specific cookies to prevent cross-tab overwrites in private mode.
    """

    def process_request(self, request):
        """
        Load the session for the request.
        For game-related requests, only uses session-specific cookies (sessionid_<session_key>).
        Validates clueless_user_* cookies against session's expected_username before loading session.
        For non-game requests, tries session-specific cookies first, then falls back to generic 'sessionid'.
        Logs and clears any unexpected 'sessionid' or stale session-specific cookies.
        """
        # Determine if this is a game-related request
        is_game_request = request.path.startswith(('/game/', '/login/', '/logout/', '/start_game/', '/ws/game/'))

        # Initialize session key
        session_key = None
        cookies = request.COOKIES

        # Log cookies for debugging
        if DEBUG:
            print("[CustomSessionMiddleware.process_request] Cookie details:")
            print(f"  Path: {request.path}")
            print(f"  Is game request: {is_game_request}")
            print(f"  sessionid: {cookies.get('sessionid', 'None')}")
            for key in cookies:
                if key.startswith('sessionid_') or key.startswith('clueless_user_'):
                    print(f"  {key}: {cookies[key]}")

        # For game requests, only use session-specific cookie
        if is_game_request:
            # Log warning if generic sessionid is present and ignore it
            if 'sessionid' in cookies:
                if DEBUG:
                    print(
                        "[CustomSessionMiddleware.process_request] Warning: Ignoring generic sessionid cookie for game request:")
                    print(f"  sessionid: {cookies['sessionid']}")
            for key in cookies:
                if key.startswith('sessionid_'):
                    session_key = cookies[key]
                    break
            if not session_key:
                if DEBUG:
                    print("[CustomSessionMiddleware.process_request] No session-specific cookie found for game request")
                request.session = SessionStore()
                return
        else:
            # For non-game requests, try session-specific first, then generic
            for key in cookies:
                if key.startswith('sessionid_'):
                    session_key = cookies[key]
                    break
            if not session_key:
                session_key = cookies.get(settings.SESSION_COOKIE_NAME)

        # Load session and validate for game requests
        if session_key:
            try:
                request.session = SessionStore(session_key=session_key)
                request.session.accessed = True
                # For game requests, validate all clueless_user_* cookies against expected_username
                if is_game_request:
                    expected_username = request.session.get('expected_username')
                    if not expected_username:
                        if DEBUG:
                            print("[CustomSessionMiddleware.process_request] Missing expected_username in session:")
                            print(f"  Session key: {session_key}")
                        logout(request)
                        request.session.flush()
                        request.session = SessionStore()
                        return
                    # Check all clueless_user_* cookies
                    user_cookie_found = False
                    for key in cookies:
                        if key.startswith('clueless_user_'):
                            user_session_key = key[len('clueless_user_'):]
                            if user_session_key == session_key:
                                clueless_user = cookies[key]
                                user_cookie_found = True
                                if clueless_user != expected_username:
                                    if DEBUG:
                                        print("[CustomSessionMiddleware.process_request] Session user mismatch:")
                                        print(f"  Session key: {session_key}")
                                        print(f"  Expected username: {expected_username}")
                                        print(f"  Got clueless_user: {clueless_user}")
                                    logout(request)
                                    request.session.flush()
                                    request.session = SessionStore()
                                    return
                    if not user_cookie_found:
                        if DEBUG:
                            print("[CustomSessionMiddleware.process_request] No matching clueless_user cookie found:")
                            print(f"  Session key: {session_key}")
                            print(f"  Expected username: {expected_username}")
                        logout(request)
                        request.session.flush()
                        request.session = SessionStore()
                        return
                if DEBUG:
                    print("[CustomSessionMiddleware.process_request] Session loaded:")
                    print(f"  Session key: {session_key}")
            except Exception as e:
                if DEBUG:
                    print("[CustomSessionMiddleware.process_request] Failed to load session:")
                    print(f"  Session key: {session_key}")
                    print(f"  Error: {str(e)}")
                request.session = SessionStore()
        else:
            request.session = SessionStore()
            if DEBUG:
                print("[CustomSessionMiddleware.process_request] No session key found, using new session")

    def process_response(self, request, response):
        """
        Save the session and set cookies.
        Sets session-specific cookies for the current session.
        Sets generic 'sessionid' cookie only for non-game requests.
        Clears 'sessionid' and stale session-specific cookies for game requests to prevent reuse.
        """
        try:
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            if DEBUG:
                print("[CustomSessionMiddleware.process_response] No session available:")
                print(f"  Path: {request.path}")
            return response

        # Determine if this is a game-related request
        is_game_request = request.path.startswith(('/game/', '/login/', '/logout/', '/start_game/', '/ws/game/'))

        # Log response details
        if DEBUG:
            print("[CustomSessionMiddleware.process_response] Processing response:")
            print(f"  Path: {request.path}")
            print(f"  Is game request: {is_game_request}")
            print(f"  Session modified: {modified}")
            print(f"  Session empty: {empty}")

        if empty:
            # Delete all session-related cookies
            response.delete_cookie(settings.SESSION_COOKIE_NAME, path=settings.SESSION_COOKIE_PATH)
            for key in [k for k in request.COOKIES.keys() if k.startswith('sessionid_')]:
                response.delete_cookie(key, path=settings.SESSION_COOKIE_PATH)
            for key in [k for k in request.COOKIES.keys() if
                        k.startswith(('clueless_session_', 'clueless_browser_', 'clueless_user_', 'clueless_token_'))]:
                response.delete_cookie(key, path=settings.SESSION_COOKIE_PATH)
            if DEBUG:
                print("[CustomSessionMiddleware.process_response] Session empty, cookies deleted:")
                print(f"  sessionid: deleted")
                print(f"  sessionid_*: deleted")
                print(f"  clueless_*: deleted")
        else:
            # Save the session if modified or required
            if modified or settings.SESSION_SAVE_EVERY_REQUEST:
                try:
                    request.session.save()
                    session_key = request.session.session_key
                    # Set session-specific cookie
                    response.set_cookie(
                        f'sessionid_{session_key}',
                        session_key,
                        max_age=settings.SESSION_COOKIE_AGE,
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path=settings.SESSION_COOKIE_PATH,
                        secure=settings.SESSION_COOKIE_SECURE,
                        httponly=settings.SESSION_COOKIE_HTTPONLY,
                        samesite=settings.SESSION_COOKIE_SAMESITE
                    )
                    # Set generic sessionid cookie only for non-game requests
                    if not is_game_request:
                        response.set_cookie(
                            settings.SESSION_COOKIE_NAME,
                            session_key,
                            max_age=settings.SESSION_COOKIE_AGE,
                            domain=settings.SESSION_COOKIE_DOMAIN,
                            path=settings.SESSION_COOKIE_PATH,
                            secure=settings.SESSION_COOKIE_SECURE,
                            httponly=settings.SESSION_COOKIE_HTTPONLY,
                            samesite=settings.SESSION_COOKIE_SAMESITE
                        )
                    # Clear generic sessionid and stale session-specific cookies for game requests
                    else:
                        response.delete_cookie(settings.SESSION_COOKIE_NAME, path=settings.SESSION_COOKIE_PATH)
                        # Clear any session-specific cookies that don't match the current session
                        for key in [k for k in request.COOKIES.keys() if
                                    k.startswith('sessionid_') and k != f'sessionid_{session_key}']:
                            response.delete_cookie(key, path=settings.SESSION_COOKIE_PATH)
                        for key in [k for k in request.COOKIES.keys() if k.startswith(('clueless_session_',
                                                                                       'clueless_browser_',
                                                                                       'clueless_user_',
                                                                                       'clueless_token_')) and not k.endswith(
                                session_key)]:
                            response.delete_cookie(key, path=settings.SESSION_COOKIE_PATH)
                    if DEBUG:
                        print("[CustomSessionMiddleware.process_response] Cookies set:")
                        print(f"  sessionid_{session_key}: {session_key}")
                        if not is_game_request:
                            print(f"  sessionid: {session_key}")
                        else:
                            print("  sessionid: deleted")
                            print("  stale sessionid_*: deleted")
                            print("  stale clueless_*: deleted")
                except Exception as e:
                    if DEBUG:
                        print("[CustomSessionMiddleware.process_response] Failed to save session:")
                        print(f"  Error: {str(e)}")

        return response