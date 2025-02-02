
# My Flask App

## Live Site

https://code-institute-433215.uc.r.appspot.com/


This is a simple Flask application with static files and API views.

## Prerequisites

- Python 3.9 or higher
- Google Cloud SDK (for deployment to Google App Engine)
- Virtual environment tools (optional but recommended)

## Setting Up the Project

1. Clone the repository:

   git clone git@github.com:vinnieOrdobas/ci_national_ai.git
   cd ci_national_ai

2. Create and activate a virtual environment (optional but recommended):

   python3 -m venv venv
   source venv/bin/activate  # On Windows use venv\Scripts\activate

3. Install the required dependencies:

   cd src/
   pip install -r requirements.txt

## Running the Application Locally

To run the Flask application locally:

   export FLASK_APP=server:app
   cd src/
   flask run

The application will be available at http://127.0.0.1:5000.



## Deploying to Google App Engine

Note: Instructions on installing gcloud are here: https://cloud.google.com/sdk/docs/install-sdk

1. Ensure you are in the project root directory:

   cd ci_national_ai

2. Add Env Vars to env_variables.yaml file.
   Alter values as appropriate for PROJECT_ID, LOCATION, ENDPOINT_ID, MAPBOX_TOKEN

3. Deploy the application to Google App Engine:

   cd src/
   gcloud app deploy

4. Access the deployed application at https://<your-project-id>.appspot.com.

### Google App Engine Configuration

- The app.yaml file is configured to run the application using Gunicorn and handle static files.
- The entry point for the application is specified as wsgi:app.

## Troubleshooting

- Service Unavailable: If you encounter a "Service Unavailable" error, check the Google Cloud Console logs under Logging > Logs Explorer.
- Permission Errors: Ensure that the Google App Engine service account has the necessary permissions, especially if your application interacts with Google Cloud Storage or other Google Cloud services.

