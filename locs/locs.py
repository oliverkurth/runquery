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
import time

CLIENT_ID='3724'
CLIENT_SECRET='STRAVA_CLIENT_SECRET'

bp = Blueprint('locs', __name__)

main_menu = [
        {"name" : "settings", "link" : "/settings", "label" : "Settings"},
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
    page = request.args.get('page')
    client = Client()
    token_struct = client.exchange_code_for_token(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        code=code
    )
    session['token_struct'] = token_struct
    return redirect(page, code=302)

def strava_login(page=None):
    client = Client()
    url = url_for('locs.authorized', _external=True, page=page)
    authorize_url = client.authorization_url(
        scope='activity:read_all',
        client_id=CLIENT_ID,
        redirect_uri=url)

    return redirect(authorize_url, code=302)

def refresh_token(client):
    token_struct = session.get('token_struct')
    try:
        expires_at = token_struct['expires_at']
        refresh_token=token_struct['refresh_token']
    except KeyError:
        raise NoToken
    if time.time() > expires_at:
        refresh_response = client.refresh_access_token(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            refresh_token=refresh_token)
        session['token_struct'] = refresh_response
        print("refreshed token = {}".format(refresh_response))

def create_context():
    token_struct = session.get('token_struct')
    if token_struct == None:
        raise NoToken

    try:
        access_token=token_struct['access_token']
    except KeyError:
        raise NoToken

    client = Client(access_token=access_token)
    try:
        refresh_token(client)
        athlete = client.get_athlete()
    except AccessUnauthorized:
        raise

    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    if not os.path.isdir(athlete_dir):
        os.makedirs(athlete_dir)

    return client, athlete

def get_saved_activity_ids(athlete):
    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    activities_dir = os.path.join(athlete_dir, 'activities')

    files = glob.glob(os.path.join(activities_dir, "*.json"))
    ids = [int(os.path.basename(fname).split('.')[0]) for fname in files]
    ids.sort()

    return ids

def refresh_activities(client, athlete, force=False, all=False):
    print("refreshing activities, force={}, all={}".format(force, all))

    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    activities_dir = os.path.join(athlete_dir, 'activities')
    if not os.path.isdir(activities_dir):
        os.makedirs(activities_dir)

    completed_file = os.path.join(activities_dir, 'COMPLETE')
    if not force:
        if os.path.isfile(completed_file):
            with open(completed_file) as f:
                last_sync = int(f.read() or 0)
                if (int(time.time()) - last_sync) < 3600:
                    print("last refresh was less than 3600 seconds ago and force=False")
                    return

    last_start_time = None
    if not all:
        ids = get_saved_activity_ids(athlete)
        last_id = ids[-1]
        with open(os.path.join(activities_dir, '{}.json'.format(last_id)), 'r') as f:
            a = json.load(f)
            last_start_time = datetime.strptime(a['start_date'], '%Y-%m-%dT%H:%M:%S+00:00')
            print("last start time was {} ({})".format(a['start_date'], last_start_time))

    activities = client.get_activities(limit=200, after=last_start_time)
    count = 0
    for activity in activities:
        with open(os.path.join(activities_dir, '{}.json'.format(activity.id)), 'w') as f:
            json.dump(activity.to_dict(), f)
        count = count + 1
    print("retrieved {} activities".format(count))

    # timestamp into file
    with open(completed_file, 'w') as f:
        f.write('{}'.format(int(time.time())))

def load_activities(client, athlete, num=25, start=0):
    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    activities_dir = os.path.join(athlete_dir, 'activities')

    ids = get_saved_activity_ids(athlete)
    ids = ids[::-1]            # reverse
    ids = ids[start:start+num] # slice

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
    page = request.args.get('page')
    return strava_login(page=page)

@bp.route('/settings')
def show_settings():

    try:
        client, athlete = create_context()
        return render_template(
                               'locs/settings.html', a=athlete,
                               menu=main_menu, active_name='settings')
    except (NoToken, AccessUnauthorized):
        return strava_login('/settings')


@bp.route('/athlete')
def show_athlete():
    try:
        client, athlete = create_context()
        return render_template(
                               'locs/athlete.html', a=athlete,
                               menu=main_menu, active_name='athlete')
    except (NoToken, AccessUnauthorized):
        return strava_login('/athlete')

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

        athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
        activities_dir = os.path.join(athlete_dir, 'activities', 'detailed')
        if not os.path.isdir(activities_dir):
            os.makedirs(activities_dir)

        activity = client.get_activity(id)
        with open(os.path.join(activities_dir, '{}.json'.format(activity.id)), 'w') as f:
            json.dump(activity.to_dict(), f)
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

@bp.route('/api/sync_activities')
def api_sync_activities():
    sync_all = {'true' : True, 'false' : False}[request.args.get('all').lower()]
    try:
        client, athlete = create_context()
        refresh_activities(client, athlete, force=True, all=sync_all)
        return json.dumps({'success':'ok'})
    except (NoToken, AccessUnauthorized):
        return json.dumps({'error' : 'unauthorized'}), 401

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

