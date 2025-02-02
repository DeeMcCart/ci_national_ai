#!/bin/bash
set -e

export PROJECT_ID=
export LOCATION=
export ENDPOINT_ID=


flask --app server  --debug run
