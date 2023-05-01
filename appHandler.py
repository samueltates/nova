from quart import Quart, render_template, websocket, request, jsonify
from quart_cors import cors
app = Quart(__name__)
app = cors(app, allow_origin="*")