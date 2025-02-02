
import os
from flask import Flask, jsonify
from flask import redirect, url_for

from hackathon.client_bp import client_bp


app = Flask(__name__)
app.register_blueprint(client_bp)

@app.route('/api/env', methods=['GET'])
def get_env_vars():
    # Fetch environment variables
    mapbox_token = os.environ['MAPBOX_TOKEN']
    print("mapbox_token", mapbox_token)
    return jsonify({
        'MAPBOX_TOKEN': mapbox_token
    })

@app.route("/")
def root():
    return redirect(url_for('clientui.client_root'))
