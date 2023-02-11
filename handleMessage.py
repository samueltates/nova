from .nova import *
from http.server import BaseHTTPRequestHandler
import json


class handler(BaseHTTPRequestHandler):

    def do_POST(self):

        # gets body from message, needs length of file and reads that length
        # not sure why this is so it doesn't go forever I guess
        content_len = int(self.headers['content-length'])
        post_body = self.rfile.read(content_len)
        post_body_py = json.loads(post_body)
        parseInput(post_body_py)
        print(post_body_py["sessionID"])
        # will need to wait for runningPrompts to be populated
        # which means probably the brain can handle the 'response'
        while functionsRunning > 0:
            print('waiting for functions to finish')
            print(functionsRunning)
            pass
        match post_body_py["action"]:
            case "getPrompts":
                responseJson = json.dumps(
                    runningPrompts[post_body_py["sessionID"]])
            case "sendInput":
                responseJson = json.dumps(logs[post_body_py["sessionID"]])
            # case "addCartridge":
        print('printing prompts pulled from running??')

        content = bytes(responseJson, 'utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)
        return
