from quart import websocket
import json
import requests

SLACK_BOT_TOKEN = "q2JOz07cXRkHFPQrg2fRsMuu"
RTM_START_URL = "https://slack.com/api/rtm.connect"

# Obtain WebSocket URL from Slack
resp = requests.post(RTM_START_URL, headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"})
ws_url = resp.json().get("url")

# Connect to WebSocket
ws = websocket.WebSocketApp(ws_url,
                            on_message=lambda ws, msg: on_message(ws, msg),
                            on_error=lambda ws, err: on_error(ws, err),
                            on_close=lambda ws: on_close(ws))

# Define event handlers
def on_message(ws, message):
    message = json.loads(message)
    print(message)
    if message.get("type") == "message" and not message.get("is_read"):
        # Here you can handle unread messages
        pass

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws):
    print("### closed ###")

# Run WebSocket
ws.run_forever()
