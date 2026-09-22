from functools import wraps

from flask import redirect, request, session, url_for


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped
