from flask import Flask
from flask import request


app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route('/hello', methods=['POST', 'GET'])
def login():
    error = None
    return '<p> maybe baby</p>'

    if request.method == 'POST':
        print('post')
        return '<p> tony time</p>'
        # if valid_login(request.form['username'],
        #                request.form['password']):
        #     return log_the_user_in(request.form['username'])
        # else:
            # error = 'Invalid username/password'
    else:
        print('get')
        return '<p> toon time</p>'

    # the code below is executed if the request method
    # was GET or the credentials were invalid
    # return render_template('login.html', error=error)