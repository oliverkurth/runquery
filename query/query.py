#!/usr/bin/env python

import stravalib
from stravalib.client import Client
from stravalib.exc import AccessUnauthorized, ObjectNotFound
from stravalib import unithelper
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
import os
import glob
import json
from datetime import datetime
import time

CLIENT_ID='3724'
CLIENT_SECRET=os.getenv('STRAVA_CLIENT_SECRET')

bp = Blueprint('query', __name__)

main_menu = [
        {"name" : "settings", "link" : "/settings", "label" : "Settings"},
        {"name" : "search", "link" : "/search", "label" : "Search"},
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
    url = url_for('query.authorized', _external=True, page=page)
    authorize_url = client.authorization_url(
        scope=['profile:read_all','activity:read_all'],
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

    with open(os.path.join(athlete_dir, 'athlete.json'), 'w') as f:
        json.dump(athlete.to_dict(), f)

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

    activities = client.get_activities(after=last_start_time)
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
    if num != None:
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

def activity_dict(athlete, a):
    if athlete.measurement_preference == 'feet':
        distance = str(unithelper.miles(a.distance))
        gain = str(unithelper.feet(a.total_elevation_gain))
        if a.type == 'Ride':
            speed = str(unithelper.mph(a.average_speed))
        else:
            try:
                speed = "{0:.2f} /mi".format(60/(unithelper.mph(a.average_speed).num))
            except ZeroDivisionError:
                speed = 'NaN'
    else:
        distance = str(unithelper.kilometers(a.distance))
        gain = str(unithelper.meters(a.total_elevation_gain))
        if a.type == 'Ride':
            speed = str(unithelper.kph(a.average_speed))
        else:
            try:
                speed = "{0:.2f} /km".format(60/(unithelper.kph(a.average_speed).num))
            except ZeroDivisionError:
                speed = 'NaN'

    date = a.start_date_local.strftime(athlete.date_preference or "%a, %d %b %Y")

    return {
            'link' : url_for('query.show_activity', id=a.id),
            'strava_link' : 'https://www.strava.com/activities/{}'.format(a.id),
            'name' : a.name,
            'type' : a.type,
            'date' : date,
            'distance' : distance,
            'gain' : gain,
            'elapsed_time' : str(a.elapsed_time),
            'moving_time' : str(a.moving_time),
            'speed' : speed,
            'start_latlng' : [a.start_latitude, a.start_longitude],
            'polyline' : a.map.polyline or a.map.summary_polyline
        }

@bp.route('/login')
def show_login():
    page = request.args.get('page') or '/search'
    return strava_login(page=page)

@bp.route('/settings')
def show_settings():
    try:
        client, athlete = create_context()
        return render_template(
                               'query/settings.html', a=athlete,
                               menu=main_menu, active_name='settings')
    except (NoToken, AccessUnauthorized):
        return strava_login('/settings')

@bp.route('/activity')
def show_activity():
    id = request.args.get('id')
    try:
        client, athlete = create_context()

        athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
        activities_dir = os.path.join(athlete_dir, 'activities', 'detailed')
        if not os.path.isdir(activities_dir):
            os.makedirs(activities_dir)

        filename = os.path.join(activities_dir, '{}.json'.format(id))
        if os.path.isfile(filename):
            with open(filename, 'r') as f:
                activity = stravalib.model.Activity()
                activity.from_dict(json.load(f))
        else:
            activity = client.get_activity(id)
            with open(os.path.join(activities_dir, '{}.json'.format(activity.id)), 'w') as f:
                json.dump(activity.to_dict(), f)
        activity.id = id
        return render_template(
                               'query/activity.html', a=activity_dict(athlete, activity),
                               menu=main_menu, active_name='search')

    except NoToken:
        return strava_login()
    except AccessUnauthorized:
        return strava_login()
    except ObjectNotFound:
        return render_template('404.html', object="activity",
                               menu=main_menu, active_name='search'), 404

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
    try:
        client, athlete = create_context()
        refresh_activities(client, athlete)
        activities = load_activities(client, athlete, num=None)

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

        if athlete.measurement_preference == 'feet':
            dist_unit = unithelper.miles
            gain_unit = unithelper.feet
        else:
            dist_unit = unithelper.kilometers
            gain_unit = unithelper.meters

        min_dist = dist_unit(float(filter.get('min_dist') or 0))
        max_dist = dist_unit(float(filter.get('max_dist') or 0))
        min_gain = gain_unit(float(filter.get('min_gain') or 0))
        max_gain = gain_unit(float(filter.get('max_gain') or 0))

        bounds = None
        if filter.get('within_bounds'):
            bounds = filter.get('mapbounds')
            bounds = [ bounds['_southWest']['lat'], bounds['_southWest']['lng'],
                       bounds['_northEast']['lat'], bounds['_northEast']['lng'] ]

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

            if min_dist > dist_unit(0):
                if a.distance < min_dist:
                    continue

            if max_dist > dist_unit(0):
                if a.distance > max_dist:
                    continue

            if min_gain > gain_unit(0):
                if a.total_elevation_gain < min_gain:
                    continue

            if max_gain > gain_unit(0):
                if a.total_elevation_gain > max_gain:
                    continue

            if bounds != None:
                lat = a.start_latitude
                lng = a.start_longitude
                if lat < bounds[0] or lng < bounds[1] or \
                   lat > bounds[2] or lng > bounds[3] :
                    continue

            matched.append(a)

        results = []
        for m in matched:
            results.append(activity_dict(athlete, m))
 
        return(json.dumps(results))
    except (NoToken, AccessUnauthorized):
        return json.dumps({'error' : 'unauthorized'}), 401

@bp.route('/search')
def show_search():

    return render_template('query/search.html',
                           menu=main_menu, active_name='search')

