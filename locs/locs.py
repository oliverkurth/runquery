#!/usr/bin/env python

import stravalib
from stravalib.client import Client
from stravalib.exc import AccessUnauthorized, ObjectNotFound
import polyline
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
import functools
import os
import glob
import json
from datetime import datetime

CLIENT_ID='3724'
CLIENT_SECRET='STRAVA_CLIENT_SECRET'

bp = Blueprint('locs', __name__)

main_menu = [
        {"name" : "main", "link" : "/", "label" : "Main"},
        {"name" : "athlete", "link" : "/athlete", "label" : "Athlete"},
        {"name" : "activities", "link" : "/activities", "label" : "Activities"},
        {"name" : "search", "link" : "/search", "label" : "Search"},
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
        scope='activity:read_all',
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
        activity = stravalib.model.Activity()
        activity.from_dict(d)
        activity.id = id
        activities.append(activity)

    return activities

@bp.route('/login')
def show_login():
    return strava_login()

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

@bp.route('/api/set_search', methods=['POST'])
def api_set_search():

    filter = request.get_json(force=True)
    print(filter)
    try:
        client, athlete = create_context()
        refresh_activities(client, athlete)
        activities = load_activities(client, athlete, num=200)

        title_words = (filter.get('title_words') or '').strip().split()
        title_words = [w.lower() for w in title_words] 

        have_type = False
        for type in ['run', 'ride', 'hike', 'walk']:
            flag = filter.get('type_' + type)
            if flag:
                have_type = True
                break

        date_before = None
        if filter.get('date_before'):
            date_before = datetime.strptime(filter.get('date_before'), '%Y-%m-%d')

        date_after = None
        if filter.get('date_after'):
            date_after = datetime.strptime(filter.get('date_after'), '%Y-%m-%d')

        min_dist = int(filter.get('min_dist') or 0)
        max_dist = int(filter.get('max_dist') or 0)
        min_gain = int(filter.get('min_gain') or 0)
        max_gain = int(filter.get('max_gain') or 0)

        #matched = activities
        matched = []
        for a in activities:
            if len(title_words) > 0:
                all_found = True
                for w in title_words:
                    if not w in a.name.lower():
                        all_found = False
                        break
                if not all_found:
                    continue

            if have_type:
                is_type = False
                for t in ['run', 'ride', 'hike', 'walk']:
                    if str(a.type).lower() == t and filter.get('type_' + t):
                        is_type = True
                        break
                if not is_type:
                    continue

            if date_before:
                if a.start_date_local > date_before:
                    continue

            if date_after:
                if a.start_date_local < date_after:
                    continue

            if min_dist > 0:
                if int(a.distance) < min_dist:
                    continue

            if max_dist > 0:
                if int(a.distance) > min_dist:
                    continue

            if min_gain > 0:
                if int(a.total_elevation_gain) < min_gain:
                    continue

            if max_gain > 0:
                if int(a.total_elevation_gain) > max_gain:
                    continue

            matched.append(a)

        results = []
        for m in matched:
            results.append({
                'link' : 'https://www.strava.com/activities/{}'.format(m.id),
                'name' : m.name,
                'type' : m.type,
                'date' : m.start_date_local.strftime("%a, %d %b %Y"),
                'distance' : int(m.distance),
                'gain' : int(m.total_elevation_gain),
                'start_latlng' : [m.start_latitude, m.start_longitude]
            })
 
        return(json.dumps(results))
    except (NoToken, AccessUnauthorized):
        return json.dumps({'error' : 'unauthorized'}), 401

@bp.route('/search')
def show_search():

    return render_template('locs/search.html',
                           menu=main_menu, active_name='search')

@bp.route('/map')
def show_map():
    try:
        client, athlete = create_context()
        refresh_activities(client, athlete)
        activities = load_activities(client, athlete, num=200)

        start_points = []
        for a in activities:
            line = polyline.decode(a.map.summary_polyline)
            start_points.append(line[0])

        return render_template(
                               'locs/map.html',
                               activities=activities,
                               ids=[a.id for a in activities],
                               dates = [a.start_date_local.strftime("%a, %d %b %Y") for a in activities],
                               names=[a.name for a in activities],
                               start_points=start_points,
                               menu=main_menu, active_name='map')

    except NoToken:
        return strava_login()
    except AccessUnauthorized:
        return strava_login()

