import os
import requests
import math
from flask import redirect, url_for, session, Response
from chatterbot import ChatBot
from chatterbot.trainers import ChatterBotCorpusTrainer
import nltk
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from flask import Flask, render_template, request
from dotenv import load_dotenv
from chatbot import get_chatbot_response

# Initialize dotenv
load_dotenv()

# Database engine
engine = create_engine('sqlite:///my_database.db', connect_args={'check_same_thread': False})

# Database session
Session = scoped_session(sessionmaker(bind=engine))

# Initialize the chatbot and train it.
nltk.download('punkt')
chatbot = ChatBot("WeatherBot")
trainer = ChatterBotCorpusTrainer(chatbot)
trainer.train("chatterbot.corpus.english", "corpus/weather_corpus.yml")

# Initialize the Flask application and set the folder for HTML templates.
app = Flask(__name__, template_folder='templates')

# API keys
app.secret_key = os.environ.get('SECRET_KEY')
point_forcast_api_key = os.environ.get('point_forcast_api_key')
map_key = os.environ.get('MAP_KEY')
open_weather_api_key = os.environ.get('open_weather_api_key')


@app.route('/handle_chatbot_response', methods=['POST'])
def handle_chatbot_response():
    user_input = request.form['user_text']
    bot_response = get_chatbot_response(user_input)  # Call the function from chatbot.py
    response = Response(bot_response)
    response.headers['Content-Type'] = 'text/plain'

    return response


# Database connection
@app.teardown_appcontext
def shutdown_session(exception=None):
    Session.remove()


# Function to convert temperature from Kelvin to Celsius.
def kelvin_to_celsius(kelvin):
    """Convert Kelvin to Celsius."""
    return kelvin - 273.15 if kelvin else None


# Function to calculate wind speed from its vector components (u and v).
def calculate_wind_speed(u, v):
    """Calculate wind speed from its vector components."""
    return math.sqrt(u ** 2 + v ** 2) if u and v else None


def degrees_to_cardinal(d):
    """
    Converts degrees to cardinal directions.

    Parameters:
    - d: The degree to be converted.

    Returns:
    - A string representing the cardinal direction.
    """
    dirs = ["North", "North-East", "East", "South-East", "South", "South-West", "West", "North-West"]
    ix = round(d / (360. / len(dirs)))
    return dirs[ix % len(dirs)]


# Function to calculate wind direction in degrees from its vector components (u and v)
def calculate_wind_direction(u, v):
    """Calculate wind direction in degrees from its vector components."""
    return (180 / math.pi * math.atan2(u, v) + 360) % 360 if u and v else None


# Route for the home page of the website.
@app.route('/')
def home():
    return render_template('index.html')


# Mapping of precipitation types from integer to description
precipitation_type_map = {
    0: "No precipitation",
    1: "Rain",
    3: "Freezing rain",
    5: "Snow",
    7: "Mixture of rain and snow",
    8: "Ice pellets"
}


# Route to handle the 'get_weather' request, process it, and display the result.
@app.route('/get_weather', methods=['POST'])
def get_weather():
    # Extract and process location data from the form submission.
    location = request.form['location']
    location_name, coords = location.split('|')
    latitude, longitude = [float(coord) for coord in coords.split(',')]
    if latitude is not None and longitude is not None:
        # Fetch weather data using the coordinates.
        weather_data = fetch_weather_data(latitude, longitude)
        if weather_data:
            # Format and process the weather data.
            temperature_celsius = kelvin_to_celsius(weather_data.get('temp-surface', [None])[0])
            if temperature_celsius is not None:
                temperature_celsius = round(temperature_celsius, 2)

            u_component = weather_data.get('wind_u-surface', [None])[0]
            v_component = weather_data.get('wind_v-surface', [None])[0]
            wind_speed = calculate_wind_speed(u_component, v_component)
            if wind_speed is not None:
                wind_speed = round(wind_speed, 2)

            wind_direction_degrees = calculate_wind_direction(u_component, v_component)
            wind_direction_compass = None
            if wind_direction_degrees is not None:
                wind_direction_degrees = round(wind_direction_degrees, 2)
                wind_direction_compass = degrees_to_cardinal(wind_direction_degrees)

            precipitation_values = weather_data.get('past3hprecip-surface', [])
            if precipitation_values:
                total_precipitation = sum(precipitation_values)
                precipitation = f"{round(total_precipitation, 2)}"
            else:
                precipitation = "None"

            precipitation_type = weather_data.get('ptype-surface', [None])[0]
            if precipitation_type is not None:
                # Convert integer to corresponding precipitation description
                precipitation_type = precipitation_type_map.get(precipitation_type, "Unknown")
            else:
                precipitation_type = "None"

            # Save the processed data in the session and redirect to the weather result page.
            session['weather_data'] = {
                'temp': temperature_celsius,
                'humidity': round(weather_data.get('rh-surface', [None])[0], 2)
                if weather_data.get('rh-surface', [None])[0] is not None else None,
                'pressure': round(weather_data.get('pressure-surface', [None])[0], 2)
                if weather_data.get('pressure-surface', [None])[0] is not None else None,
                'wind_speed': wind_speed,
                'wind_direction': wind_direction_degrees,
                'wind_direction_compass': wind_direction_compass,
                'precipitation': precipitation,
                'ptype': precipitation_type,
                'lat': latitude,
                'lon': longitude,
                'location_name': location_name,
            }

        return redirect(url_for('weather_result'))
    # Return an error if location is not found.
    else:
        return 'Location not found', 404


# Route to display the weather results.
@app.route('/weather_result')
def weather_result():
    # Retrieve weather data from the session and render the weather result page.
    weather_data = session.get('weather_data', None)
    current_year = datetime.now().year
    return render_template('weather.html', weather=weather_data, map_key=map_key, current_year=current_year)


# Function to fetch weather data from the Windy.com API.
def fetch_weather_data(latitude, longitude):
    # Define the API endpoint and request headers.
    url = "https://api.windy.com/api/point-forecast/v2"
    headers = {'Content-Type': 'application/json'}
    # Prepare the payload for the API request.
    payload = {
        "lat": latitude,
        "lon": longitude,
        "model": "gfs",
        "parameters": ["temp", "rh", "pressure", "wind", "precip", "ptype"],
        "levels": ["surface"],
        "key": point_forcast_api_key
    }
    # Make the API request and return the response data.
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        return None


# Run the Flask app
if __name__ == "__main__":
    app.run()
