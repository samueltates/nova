import os
from quart import Quart, render_template, websocket, request, jsonify
from quart_cors import cors

app = Quart(__name__)
app.session = None
app.config['DEBUG'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SESSION_TYPE'] = 'redis'
# app.config["REDIS_URI"] = os.environ.get('REDIS_URI')
# app.config["REDIS_PORT"] = 6379
app.config['CORS_ALLOW_HEADERS'] = "Content-Type, Authorization"
app.config['CORS_ALLOW_ORIGINS'] = os.environ.get("CORS_ALLOWED_ORIGINS")
app.config['CORS_SUPPORTS_CREDENTIALS'] = True
app.config['CORS_METHODS'] = "GET, POST, PUT, DELETE, OPTIONS"
app.config['CORS_ALLOW_CREDENTIALS'] = True
app.config["SESSION_COOKIE_SAMESITE"] = None
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE')  # Set to True if using HTTPS!
app.config["WEBSOCKET_MAX_SIZE"] = 1024 * 1024 * 100  # Maximum size set to 1MB (adjust as needed)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 100  # Setting the maximum request size to 100MB
app = cors(app)
