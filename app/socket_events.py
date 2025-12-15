from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from .extensions import socketio


@socketio.on('connect')
def on_connect():
    try:
        if getattr(current_user, 'is_authenticated', False):
            room = f'user_{current_user.id}'
            join_room(room)
            # Optional: notify the user that they are connected
            emit('connected', {'ok': True, 'room': room})
    except Exception:
        pass


@socketio.on('disconnect')
def on_disconnect():
    try:
        if getattr(current_user, 'is_authenticated', False):
            room = f'user_{current_user.id}'
            leave_room(room)
    except Exception:
        pass
