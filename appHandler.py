from quart import Quart, render_template, websocket, request, jsonify
from quart_cors import cors
app = Quart(__name__)
app = cors(app, allow_origin="*")
app.config['DEBUG'] = True
app.config["WEBSOCKET_MAX_SIZE"] = 1024 * 1024 * 100  # Maximum size set to 1MB (adjust as needed)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 100  # Setting the maximum request size to 100MB
