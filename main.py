#!/usr/bin/env python

from stravalib.client import Client
from flask import Flask
from flask import request
from flask import redirect, session
import json

app = Flask(__name__)
app.secret_key = "piesakeGhieh3xeipheifaem7eijai9e"
client = Client()
access_token = None

CLIENT_ID='3724'
CLIENT_SECRET='STRAVA_CLIENT_SECRET'

@app.route('/athlete')
def show_athlete():
    access_token = session['access_token']
    athlete = client.get_athlete()
    return json.dumps(athlete.to_dict())
#    return "Name: {}, email: {}".format(athlete.firstname, athlete.email)

@app.route('/activity')
def show_activity():
    id = request.args.get('id')
    access_token = session['access_token']
    activity = client.get_activity(id)
    return "start: {}, end: {}".format(activity.start_latlng, activity.end_latlng)
    #return json.dumps(activity.to_dict())

@app.route('/authorized')
def authorized():
    code = request.args.get('code')
    access_token = client.exchange_code_for_token(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        code=code
    )
    athlete = client.get_athlete()
    session['access_token'] = access_token
    return ("For {id}, I now have an access token {token}".format(
        id=athlete.id, token=access_token))

@app.route('/')
def index():
    authorize_url = None
    if not access_token:
        authorize_url = client.authorization_url(
            client_id=CLIENT_ID,
            redirect_uri='http://192.168.173.131:8282/authorized')
        return redirect(authorize_url, code=302)

    print access_token


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8282)

