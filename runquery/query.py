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
import shutil
import calendar
import math
import units
from bisect import bisect_left
CLIENT_ID='3724'
# we want an exception if unset
CLIENT_SECRET=os.environ['STRAVA_CLIENT_SECRET']

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

def strava_authorize_url(page=None):
    client = Client()
    url = url_for('query.authorized', _external=True, page=page)
    return client.authorization_url(
        scope=['profile:read_all','activity:read_all'],
        client_id=CLIENT_ID,
        redirect_uri=url)

def strava_login(page=None):
    authorize_url = strava_authorize_url(page)
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

def delete_athlete(athlete):
    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    if os.path.isdir(athlete_dir):
        shutil.rmtree(athlete_dir)

def get_saved_activity_ids(athlete):
    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    activities_dir = os.path.join(athlete_dir, 'activities')

    files = glob.glob(os.path.join(activities_dir, "*.json"))
    ids = [int(os.path.basename(fname).split('.')[0]) for fname in files]
    ids.sort()

    return ids

def dir_is_complete(directory, force, max_age=None):
    if not force:
        completed_file = os.path.join(directory, 'COMPLETE')
        if os.path.isfile(completed_file):
            if max_age == None:
                return True
            with open(completed_file) as f:
                last_sync = int(f.read() or 0)
                if (int(time.time()) - last_sync) < max_age:
                    print("{}: last refresh was less than {} seconds ago and force=False".format(directory, max_age))
                    return True
    return False

def dir_set_complete(directory):
    completed_file = os.path.join(directory, 'COMPLETE')
    # timestamp into file
    with open(completed_file, 'w') as f:
        f.write('{}'.format(int(time.time())))

def refresh_activities(client, athlete, force=False, all=False):
    print("refreshing activities, force={}, all={}".format(force, all))

    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    activities_dir = os.path.join(athlete_dir, 'activities')
    if not os.path.isdir(activities_dir):
        os.makedirs(activities_dir)

    if dir_is_complete(activities_dir, force, max_age=3600):
        return

    last_start_time = None
    if not all:
        ids = get_saved_activity_ids(athlete)
        if len(ids) > 0:
            last_id = ids[-1]
            with open(os.path.join(activities_dir, '{}.json'.format(last_id)), 'r') as f:
                a = json.load(f)
                last_start_time = datetime.strptime(a['start_date'], '%Y-%m-%dT%H:%M:%S+00:00')
                print("last start time was {} ({})".format(a['start_date'], last_start_time))
        else:
            print("no activities found, refreshing all")

    limit = None
    if current_app.config.get('DEBUG_MODE'):
        limit = 200

    activities = client.get_activities(after=last_start_time, limit=limit)
    count = 0
    for activity in activities:
        with open(os.path.join(activities_dir, '{}.json'.format(activity.id)), 'w') as f:
            json.dump(activity.to_dict(), f)
        count = count + 1
    print("retrieved {} activities".format(count))

    dir_set_complete(activities_dir)

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

def refresh_photos(client, athlete, activity_id, force=False, size=None):
    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    activities_dir = os.path.join(athlete_dir, 'activities')
    photos_dir = os.path.join(activities_dir, activity_id, 'photos' , '0' if size == None else str(size))

    if not os.path.isdir(photos_dir):
        os.makedirs(photos_dir)

    if dir_is_complete(photos_dir, force):
        return

    photos = client.get_activity_photos(activity_id, size)
    for photo in photos:
        with open(os.path.join(photos_dir, '{}.json'.format(photo.unique_id)), 'w') as f:
            json.dump(photo.to_dict(), f)

    dir_set_complete(photos_dir)

def load_photos(client, athlete, activity_id, size=None):
    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    activities_dir = os.path.join(athlete_dir, 'activities')
    photos_dir = os.path.join(activities_dir, activity_id, 'photos' , '0' if size == None else str(size))

    photos = []
    files = glob.glob(os.path.join(photos_dir, "*.json"))
    for fname in files:
        with open(fname, 'r') as f:
            d = json.load(f)
        photo = stravalib.model.ActivityPhoto()
        photo.from_dict(d)
        photos.append(photo)

    return photos

def refresh_streams(client, athlete, activity_id, force=False):
    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    activities_dir = os.path.join(athlete_dir, 'activities')
    streams_dir = os.path.join(activities_dir, activity_id, 'streams')

    if not os.path.isdir(streams_dir):
        os.makedirs(streams_dir)

    if dir_is_complete(streams_dir, force):
        return

    types = ['time', 'latlng']
    stream = client.get_activity_streams(activity_id, types=types)
    for type in types:
        with open(os.path.join(streams_dir, '{}.json'.format(type)), 'w') as f:
            json.dump(stream[type].to_dict(), f)

    dir_set_complete(streams_dir)

def load_streams(client, athlete, activity_id):
    athlete_dir = os.path.join(current_app.instance_path, 'athletes', str(athlete.id))
    activities_dir = os.path.join(athlete_dir, 'activities')
    streams_dir = os.path.join(activities_dir, activity_id, 'streams')

    streams = {}
    files = glob.glob(os.path.join(streams_dir, "*.json"))
    for fname in files:
        stream_type = os.path.basename(fname)[0:-5]
        if not stream_type in ['time', 'latlng']:
            current_app.logger.info("unknown stream type '{}' from {}".format(stream_type, fname))
            continue
        with open(fname, 'r') as f:
            d = json.load(f)
        stream = stravalib.model.Stream()
        stream.from_dict(d)
        streams[stream_type] = stream

    return streams

def activity_dict(athlete, a):
    elapsed_time = unithelper.seconds(a.elapsed_time.total_seconds())
    if athlete.measurement_preference == 'feet':
        distance = str(unithelper.miles(a.distance))
        gain = str(unithelper.feet(a.total_elevation_gain))
        if a.type == 'Ride':
            speed = str(unithelper.mph(a.average_speed))
            elapsed_speed = str(unithelper.mph(a.distance/elapsed_time))
        else:
            try:
                speed = "{0:.2f} /mi".format(60/(unithelper.mph(a.average_speed).num))
                elapsed_speed = "{0:.2f} /mi".format(60/unithelper.mph(a.distance/elapsed_time).num)
            except ZeroDivisionError:
                speed = 'NaN'
                elapsed_speed = 'NaN'
    else:
        distance = str(unithelper.kilometers(a.distance))
        gain = str(unithelper.meters(a.total_elevation_gain))
        if a.type == 'Ride':
            speed = str(unithelper.kph(a.average_speed))
            elapsed_speed = str(unithelper.kph(a.distance/elapsed_time))
        else:
            try:
                speed = "{0:.2f} /km".format(60/(unithelper.kph(a.average_speed).num))
                elapsed_speed = "{0:.2f} /km".format(60/unithelper.kph(a.distance/elapsed_time).num)
            except ZeroDivisionError:
                speed = 'NaN'
                elapsed_speed = 'NaN'

    date = a.start_date_local.strftime(athlete.date_preference or "%a, %d %b %Y")
    weekday = calendar.day_name[a.start_date_local.weekday()]

    workout_type = ''
    if a.type == 'Run':
        workout_type = ['', 'Race', 'Long Run', 'Workout'][int(a.workout_type or 0)]

    garmin_link = ''
    if a.external_id:
        if a.external_id.startswith('garmin_push_'):
            garmin_id = a.external_id.split('_')[2]
            garmin_link = 'https://connect.garmin.com/modern/activity/{}'.format(garmin_id)

    return {
            'id' : a.id,
            'link' : url_for('query.show_activity', id=a.id),
            'strava_link' : 'https://www.strava.com/activities/{}'.format(a.id),
            'garmin_link' : garmin_link,
            'name' : a.name,
            'type' : a.type,
            'workout_type' : workout_type,
            'date' : date,
            'weekday' : weekday,
            'distance' : distance,
            'gain' : gain,
            'elapsed_time' : str(a.elapsed_time),
            'moving_time' : str(a.moving_time),
            'speed' : speed,
            'elapsed_speed' : elapsed_speed,
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
        return strava_login(page='/settings')

def load_detailed_activity(client, athlete, id):
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

    return activity

@bp.route('/activity')
def show_activity():
    id = request.args.get('id')
    try:
        client, athlete = create_context()

        refresh_photos(client, athlete, id)
        refresh_streams(client, athlete, id)

        activity = load_detailed_activity(client, athlete, id)

        return render_template(
                               'query/activity.html', a=activity_dict(athlete, activity),
                               menu=main_menu, active_name='search')

    except (NoToken, AccessUnauthorized):
        return strava_login(page=url_for('query.show_activity', id=id))
    except ObjectNotFound:
        return render_template('404.html', object="activity",
                               menu=main_menu, active_name='search'), 404

def calc_stats(athlete, activities):
    stats = {}
    subs = ['total', 'per_activity', 'per_time', 'per_dist']
    metrics = ['dist', 'time', 'elevation']

    if athlete.measurement_preference != 'feet':
        units_used = {
            #'dist': unithelper.kilometers, # km results in 0 per_dist stats, reason unknown
            'dist': unithelper.meters,
            'time' : unithelper.seconds,
            'elevation': unithelper.meters
        }
    else:
        units_used = {
            'dist': unithelper.miles,
            'time' : unithelper.seconds,
            'elevation' : unithelper.feet
        }

    count = len(activities)

    for sub in subs:
        stats[sub] = {}
        for m in metrics:
            stats[sub][m] = units_used[m](0.0)

    stats_total = stats['total']
    for a in activities:
        stats_total['dist'] += a.distance
	stats_total['time'] += unithelper.seconds(float(a.elapsed_time.total_seconds()))
        stats_total['elevation'] += a.total_elevation_gain

    stats_count = stats['per_activity']
    for m in metrics:
        stats_count[m] = stats_total[m] / count

    stats_time = stats['per_time']
    for m in metrics:
        stats_time[m] = stats_total[m] / stats_total['time']

    stats_dist = stats['per_dist']
    for m in metrics:
        stats_dist[m] = stats_total[m] / stats_total['dist']

    stats['count'] = count

    return stats

def _seconds_to_timestr(seconds):
    seconds = int(seconds)
    h = seconds / 3600
    m = seconds / 60 % 60
    s = seconds % 60
    return '{}:{}:{}'.format(h, m, s)

def stats_localize(athlete, stats):

    if athlete.measurement_preference != 'feet':
        ath_units = {
            'dist': unithelper.kilometers,
            'time' : unithelper.seconds,
            'elevation': unithelper.meters,
            'speed': unithelper.kph,
            'pace': units.unit('min')/unithelper.kilometers,
        }
    else:
        ath_units = {
            'dist': unithelper.miles,
            'time' : unithelper.seconds,
            'elevation' : unithelper.feet,
            'speed': unithelper.mph,
            'pace': units.unit('min')/unithelper.miles
        }

    sdict = {}

    sdict_total = {}
    sdict_total['dist'] = str(ath_units['dist'](stats['total']['dist']))
    sdict_total['elevation'] = str(ath_units['elevation'](stats['total']['elevation']))
    sdict_total['time'] = _seconds_to_timestr(stats['total']['time'])
    sdict['total'] = sdict_total

    sdict_per_activity = {}
    sdict_per_activity['dist'] = str(ath_units['dist'](stats['per_activity']['dist']))
    sdict_per_activity['elevation'] = str(ath_units['elevation'](stats['per_activity']['elevation']))
    sdict_per_activity['time'] = _seconds_to_timestr(stats['per_activity']['time'])
    sdict['per_activity'] = sdict_per_activity

    sdict_per_time = {}
    sdict_per_time['speed'] = str(ath_units['speed'](stats['per_time']['dist']))
    sdict['per_time'] = sdict_per_time

    sdict_per_dist = {}
    sdict_per_dist['pace'] = str(ath_units['pace'](stats['per_dist']['time']))
    sdict['per_dist'] = sdict_per_dist

    return sdict

@bp.route('/api/sync_activities')
def api_sync_activities():
    sync_all = {'true' : True, 'false' : False}[request.args.get('all').lower()]
    try:
        client, athlete = create_context()
        refresh_activities(client, athlete, force=True, all=sync_all)
        return json.dumps({'success':'ok'})
    except (NoToken, AccessUnauthorized):
        return json.dumps({'error' : 'unauthorized'}), 401

@bp.route('/api/delete_athlete')
def api_delete_athlete():
    try:
        client, athlete = create_context()
        delete_athlete(athlete)
        return json.dumps({'success':'ok'})
    except (NoToken, AccessUnauthorized):
        return json.dumps({'error' : 'unauthorized'}), 401

# When user zoomed out of the map too far and into one
# of the parallel worlds longitudes may be out of range
def normalizeValue(value, norm):
   return (value + norm) % (norm * 2) - norm

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
            bounds = [ normalizeValue(bounds['_southWest']['lat'], 90),
                       normalizeValue(bounds['_southWest']['lng'], 180),
                       normalizeValue(bounds['_northEast']['lat'], 90),
                       normalizeValue(bounds['_northEast']['lng'], 180)]

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

	stats_localized = {}
	if len(matched) > 0:
            stats = calc_stats(athlete, matched)
	    stats_localized = stats_localize(athlete, stats)

        results = []
        for m in matched:
            results.append(activity_dict(athlete, m))
 
        return(json.dumps({'results' : results, 'stats' : stats_localized }))
    except (NoToken, AccessUnauthorized):
        return json.dumps({'error' : 'unauthorized'}), 401

def get_photo_location(activity, streams, photo):
    # time offset:
    seconds_photo = (photo.created_at - activity.start_date).seconds

    # photo taken before
    if seconds_photo < 0:
        return None

    # photo taken after activity
    time_data = streams['time'].data
    if seconds_photo > time_data[-1]:
        return None

    i = bisect_left(time_data, seconds_photo)

    return streams['latlng'].data[i]

@bp.route('/api/get_photos')
def api_get_photos():
    id = request.args.get('id')
    size = request.args.get('size')
    if size != None:
        size = int(size)
    get_latlng = request.args.get('get_latlng') or False
    try:
        client, athlete = create_context()

        refresh_photos(client, athlete, id, size)
        photos = load_photos(client, athlete, id, size)

        streams = None
        if get_latlng:
            refresh_streams(client, athlete, id)
            streams = load_streams(client, athlete, id)

        activity = load_detailed_activity(client, athlete, id)

        photo_list = []
        for photo in photos:
            latlng = None
            if get_latlng:
                latlng = get_photo_location(activity, streams, photo)
            if not latlng and photo.location:
                latlng = photo.location.split(',')
            photo_dict = {
                'unique_id': photo.unique_id,
                'latlng': latlng,
                'urls' : photo.urls,
                'caption' : photo.caption
            }
            photo_list.append(photo_dict)

        return json.dumps(photo_list)

    except (NoToken, AccessUnauthorized):
        return json.dumps({'error' : 'unauthorized'}), 401

@bp.route('/search')
def show_search():
    try:
        client, athlete = create_context()
        return render_template('query/search.html',
                               athlete=athlete, menu=main_menu, active_name='search')
    except (NoToken, AccessUnauthorized):
        return strava_login(page='/search')

@bp.route('/')
def show_index():
    try:
        client, athlete = create_context()
        return redirect('/search', code=302)
    except (NoToken, AccessUnauthorized):
        return render_template('query/connect.html', url=strava_authorize_url(page='/search'),
                               menu=main_menu, active_name='search')

