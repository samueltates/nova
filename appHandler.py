import os
from quart import Quart, render_template, websocket, request, jsonify
from quart_cors import cors
from redis import Redis

app = Quart(__name__)
app = cors(app, allow_origin="*")
app.config['DEBUG'] = False
app.secret_key = os.urandom(24)
app.session = None
app.config['SESSION_TYPE'] = 'redis'
app.config["SESSION_REDIS"] = Redis(host='localhost', port=6379)
# app.config['SESSION_COOKIE_SECURE'] = True  # Set to True if using HTTPS!
app.config["WEBSOCKET_MAX_SIZE"] = 1024 * 1024 * 100  # Maximum size set to 1MB (adjust as needed)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 100  # Setting the maximum request size to 100MB
