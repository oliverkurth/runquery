#!/usr/bin/env python

from stravalib.client import Client
from stravalib.exc import AccessUnauthorized
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
import functools
import json

CLIENT_ID='3724'
CLIENT_SECRET='STRAVA_CLIENT_SECRET'

bp = Blueprint('locs', __name__)

main_menu = [
        {"name" : "main", "link" : "/", "label" : "Main"},
        {"name" : "athlete", "link" : "/athlete", "label" : "Athlete"},
        {"name" : "map", "link" : "/map", "label" : "Map"},
]

@bp.route('/authorized')
def authorized():
    code = request.args.get('code')
    client = Client()
    token_struct = client.exchange_code_for_token(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        code=code
    )
    session['token_struct'] = token_struct
    return ("I now have an access token {token}".format(token=token_struct))

def strava_login():
    client = Client()
    authorize_url = client.authorization_url(
        client_id=CLIENT_ID,
        redirect_uri='http://192.168.173.131:8282/authorized')
    return redirect(authorize_url, code=302)

@bp.route('/athlete')
def show_athlete():
    token_struct = session.get('token_struct')
    if token_struct == None:
        return strava_login()
    client = Client(access_token=token_struct['access_token'])
    try:
        athlete = client.get_athlete()
        return render_template(
                               'locs/athlete.html',
                               menu=main_menu, active_name='athlete')
    except AccessUnauthorized:
        return strava_login()

#    return json.dumps(athlete.to_dict())
#    return "Name: {}, email: {}".format(athlete.firstname, athlete.email)

@bp.route('/map')
def show_map():
#    token_struct = session['token_struct']
#    client = Client(access_token=token_struct['access_token'])
#    athlete = client.get_athlete()
    return render_template(
                           'locs/map.html',
                           menu=main_menu, active_name='map')

@bp.route('/activity')
def show_activity():
    id = request.args.get('id')
    token_struct = session['token_struct']
    client = Client(access_token=token_struct['access_token'])
    activity = client.get_activity(id)
    return "start: {}, end: {}".format(activity.start_latlng, activity.end_latlng)
    #return json.dumps(activity.to_dict())

@bp.route('/')
def index():
    client = Client()
    if not 'token_struct' in session:
        authorize_url = client.authorization_url(
            client_id=CLIENT_ID,
            redirect_uri='http://192.168.173.131:8282/authorized')
        return redirect(authorize_url, code=302)
    return('you are authorized')
