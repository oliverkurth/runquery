#!/usr/bin/env python

from stravalib.client import Client
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
import functools
import json

CLIENT_ID='3724'
CLIENT_SECRET='STRAVA_CLIENT_SECRET'

bp = Blueprint('locs', __name__)

@bp.route('/athlete')
def show_athlete():
    token_struct = session['token_struct']
    client = Client(access_token=token_struct['access_token'])
    athlete = client.get_athlete()
    return json.dumps(athlete.to_dict())
#    return "Name: {}, email: {}".format(athlete.firstname, athlete.email)

@bp.route('/activity')
def show_activity():
    id = request.args.get('id')
    token_struct = session['token_struct']
    client = Client(access_token=token_struct['access_token'])
    activity = client.get_activity(id)
    return "start: {}, end: {}".format(activity.start_latlng, activity.end_latlng)
    #return json.dumps(activity.to_dict())

@bp.route('/authorized')
def authorized():
    code = request.args.get('code')
    client = Client()
    token_struct = client.exchange_code_for_token(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        code=code
    )
    athlete = client.get_athlete()
    session['token_struct'] = token_struct
    return ("For {id}, I now have an access token {token}".format(
        id=athlete.id, token=token_struct))

@bp.route('/')
def index():
    client = Client()
    if not 'token_struct' in session:
        authorize_url = client.authorization_url(
            client_id=CLIENT_ID,
            redirect_uri='http://192.168.173.131:8282/authorized')
        return redirect(authorize_url, code=302)
    return('you are authorized')
