# runquery
A web app that lets you search for your strava activities by location, name, distance and others

# Build

Create a file called `app.env` with your keys:

```
FLASK_APP=runquery
FLASK_ENV=development
FLASK_SECRET_KEY=<your secret flask key>
STRAVA_CLIENT_SECRET=<your secret straa client key>
SERVERNAME=<IP:PORT>
```

The `FLASK_SECRET_KEY` is a random string that you generate once. For example, you can use `pwgen 32`.

The `STRAVA_CLIENT_SECRET` is the secret key you get from strava when you register your app. See https://developers.strava.com/ .

`SERVERNAME` is the IP and port where you install your app.

## For development

`docker build -t runquery-flask -f Dockerfile.flask .`

Then test it with:

`docker run --rm -v $(pwd):/usr/src/app/ --env-file ./app.env -p 8282:8282 runquery-flask`

## For production

`docker build -t runquery .`

Then run it with:

`docker-compose up`.


