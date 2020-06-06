#!/usr/bin/env python

import stravalib
from stravalib.client import Client
from stravalib.exc import AccessUnauthorized, ObjectNotFound
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
import functools
import os
import glob
import json

CLIENT_ID='3724'
CLIENT_SECRET='STRAVA_CLIENT_SECRET'

bp = Blueprint('locs', __name__)

main_menu = [
        {"name" : "main", "link" : "/", "label" : "Main"},
        {"name" : "athlete", "link" : "/athlete", "label" : "Athlete"},
        {"name" : "activities", "link" : "/activities", "label" : "Activities"},
        {"name" : "map", "link" : "/map", "label" : "Map"},
]

# helper to create directory tree without complains when it exists:
def make_dirs(d):
    try:
        os.makedirs(d)
    except OSError, e:
        if e.errno != os.errno.EEXIST:
            raise

class NoToken(Exception):
    pass

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

def create_context():
    token_struct = session.get('token_struct')
    if token_struct == None:
        raise NoToken

    client = Client(access_token=token_struct['access_token'])

    try:
        athlete = client.get_athlete()

    except AccessUnauthorized:
        raise

    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    if not os.path.isdir(athlete_dir):
        os.makedirs(athlete_dir)

    return client, athlete

def refresh_activities(client, athlete):
    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    activities_dir = os.path.join(athlete_dir, 'activities')
    if not os.path.isdir(activities_dir):
        os.makedirs(activities_dir)

    completed_file = os.path.join(activities_dir, 'COMPLETE')
    if os.path.isfile(completed_file):
        return

    activities = client.get_activities(limit=200)
    for activity in activities:
        with open(os.path.join(activities_dir, '{}.json'.format(activity.id)), 'w') as f:
            json.dump(activity.to_dict(), f)

    # touch file
    open(completed_file, 'a').close()

# crude hack, see https://github.com/hozn/stravalib/issues/194
def fix_activity(activity):
    if not ' ' in activity['timezone']:
        activity['timezone'] = "(GMT-08:00) " + activity['timezone']

    for delta in ["elapsed_time", "moving_time"]:
        if type(activity[delta]) in [str, unicode]:
            h,m,s = activity[delta].split(':')
            activity[delta] = int(h)*3600 + int(m)*60 + int(s)

def load_activities(client, athlete, num=25, start=0):
    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    activities_dir = os.path.join(athlete_dir, 'activities')

    files = glob.glob(os.path.join(activities_dir, "*.json"))
    ids = [int(os.path.basename(fname).split('.')[0]) for fname in files]
    ids.sort()
    ids = ids[::-1]
    ids = ids[start:start+num]

    activities = []
    for id in ids:
        with open(os.path.join(activities_dir, '{}.json'.format(id)), 'r') as f:
            d = json.load(f)
#        fix_activity(d)
        activity = stravalib.model.Activity()
        activity.from_dict(d)
        activities.append(activity)

    return activities

@bp.route('/athlete')
def show_athlete():
    try:
        client, athlete = create_context()
        return render_template(
                               'locs/athlete.html', a=athlete,
                               menu=main_menu, active_name='athlete')
    except NoToken:
        return strava_login()
    except AccessUnauthorized:
        return strava_login()

#    return json.dumps(athlete.to_dict())
#    return "Name: {}, email: {}".format(athlete.firstname, athlete.email)

@bp.route('/activities')
def show_activities():
    try:
        client, athlete = create_context()

        refresh_activities(client, athlete)

        activities = load_activities(client, athlete)
        return render_template(
                               'locs/activities.html', activities=activities,
                               menu=main_menu, active_name='activities')

    except NoToken:
        return strava_login()
    except AccessUnauthorized:
        return strava_login()

@bp.route('/activity')
def show_activity():
    id = request.args.get('id')
    try:
        client, athlete = create_context()

        refresh_activities(client, athlete)

        activity = client.get_activity(id)
        print(activity.name)
        return render_template(
                               'locs/activity.html', a=activity,
                               menu=main_menu, active_name='activities')

    except NoToken:
        return strava_login()
    except AccessUnauthorized:
        return strava_login()
    except ObjectNotFound:
        return render_template('404.html', object="activity",
                               menu=main_menu, active_name='activities'), 404

@bp.route('/map')
def show_map():
#    token_struct = session['token_struct']
#    client = Client(access_token=token_struct['access_token'])
#    athlete = client.get_athlete()
    return render_template(
                           'locs/map.html',
                           menu=main_menu, active_name='map')

@bp.route('/')
def index():
    client = Client()
    if not 'token_struct' in session:
        authorize_url = client.authorization_url(
            client_id=CLIENT_ID,
            scope='scope=read_all,activity:read_all',
            redirect_uri='http://192.168.173.131:8282/authorized')
        return redirect(authorize_url, code=302)
    return('you are authorized')
