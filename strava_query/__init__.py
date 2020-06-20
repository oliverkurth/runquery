import os
from flask import Flask
import query

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ['FLASK_SECRET_KEY']
    )

    if 'SERVER_NAME' in os.environ:
        app.config['SERVER_NAME'] = os.environ['SERVER_NAME']

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    if 'INSTANCE_DIR' in os.environ:
        app.instance_path = os.environ['INSTANCE_DIR']

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    print("instance dir is {}".format(app.instance_path))

    app.register_blueprint(query.bp)

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'

    return app

app = create_app()

