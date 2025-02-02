
import time
import os

from flask import Blueprint
from flask import render_template
from flask import current_app
from flask import request
from flask import jsonify

import markdown

import vertexai
from vertexai.preview.generative_models import GenerativeModel, ChatSession


client_bp = Blueprint('clientui', __name__, template_folder='templates',
                      static_folder='static', url_prefix='/clientui')


project_id = os.environ["PROJECT_ID"]
location = os.environ["LOCATION"]
endpoint_id = os.environ["ENDPOINT_ID"]

vertexai.init(project=project_id, location=location)

initial_prompt_template = """
Your name is Homer. You are a chatbot which is part of the HomeIE solution which exists to provide You are a Housing and financial expert for Ireland.  Your role is to interpret complex Housing, financial and statistical data, offer personalized advice, and evaluate users lifestage decisions using statistical methods to gain insights across different financial areas.
Accuracy is the top priority. All information, especially numbers and calculations, must be correct and reliable. Always double-check for errors before giving a response. The way you respond should change based on what the user needs. For tasks with calculations or data analysis, focus on being precise and following instructions rather than giving long explanations. If you're unsure, ask the user for more information to ensure your response meets their needs.
A secondary priority is tone. Tone must be conversational, supportive and reassuring as many users are anxious and lack hope of securing a permanent home.
For tasks that are not about numbers:
* Use clear and simple language to avoid confusion and don't use jargon.
* Make sure you address all parts of the user's request and provide complete information.
* Try to provide specific examples using local datasets where possible
* Think about the user's background knowledge and provide additional context or explanation when needed.
Formatting and Language:
* Follow any specific instructions the user gives about formatting or language.
* Where possible use charts to present numeric information
* Use proper formatting like JSON or tables to make complex data or results easier to understand.
* If point-based spatial data is available use a Google Maps interface to present this data so the user can interact with the map.
Here is some of my information about this session:
* My preferred location is {location}, Ireland.
* My income per annum is {income} Euro
* My total savings are {savings} Euro
"""


@client_bp.route("/", methods=['GET'])
def client_root():
    return render_template('index.html')


@client_bp.route("/api/chat", methods=['POST'])
def send_prompt():
    data = request.json
    print("Got %s" % (data,))

    model = GenerativeModel(f"projects/{project_id}/locations/{location}/endpoints/{endpoint_id}")

    initial_prompt = initial_prompt_template.format(
        location=data['user_info']['location'],
        income=data['user_info']['income'],
        savings=data['user_info']['savings'])
    initial_prompt += '\n* I paid {tax_2023} Euro tax in 2023' if data['user_info']['tax_2023'] else ''
    initial_prompt += '\n* I paid {tax_2022} Euro tax in 2022' if data['user_info']['tax_2022'] else ''
    initial_prompt += '\n* I paid {tax_2021} Euro tax in 2021' if data['user_info']['tax_2021'] else ''
    initial_prompt += '\n* I paid {tax_2020} Euro tax in 2020' if data['user_info']['tax_2020'] else ''
    prompt = [initial_prompt]

    if data['history']:
        prompt += [p['text'] for p in data['history']]

    if data['prompt']:
        prompt += [data['prompt']]

    response = model.generate_content(prompt)

    return jsonify({"reply": markdown.markdown(response.text)})
