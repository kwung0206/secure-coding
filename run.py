import os

from app import create_app
from app.extensions import socketio

app = create_app()


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    socketio.run(
        app,
        host=host,
        port=port,
        debug=app.config["DEBUG"],
        allow_unsafe_werkzeug=not app.config["DEBUG"],
    )
