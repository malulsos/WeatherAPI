import os
import requests
import spacy
import dotenv
from datetime import datetime, timedelta
from dateutil.parser import parse
from chatterbot import ChatBot
from flask import session


# Load environment variables and initialize spaCy and ChatBot
dotenv.load_dotenv()
nlp = spacy.load('en_core_web_lg')
chatbot = ChatBot("WeatherBot")


# Function to get the date for a specific weekday
def extract_weather_query_details(user_input):
    doc = nlp(user_input)
    city_name = None
    time_frame = "current"
    specific_date = None
    max_temp = "max" in user_input.lower()
    min_temp = "min" in user_input.lower()

    # Extract city name and date/time frame
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]:
            city_name = ent.text
        elif ent.label_ == "DATE":
            # Enhanced date parsing logic
            parsed_date, parsed = try_parse_date(ent.text)
            if parsed:
                if datetime.today().date() <= parsed_date <= datetime.today().date() + timedelta(days=7):
                    specific_date = parsed_date
                    time_frame = "specific"
                elif parsed_date > datetime.today().date() + timedelta(days=7):
                    time_frame = 'future'
            break

    # Handling relative dates like 'the next day', 'day after tomorrow'
    if "tomorrow" in user_input.lower():
        time_frame = "tomorrow"
    elif ("next day" in user_input.lower() or "day after tomorrow" in user_input.lower() or "in two days"
          in user_input.lower() or "day after" in user_input.lower()):
        specific_date = datetime.today().date() + timedelta(days=2)
        time_frame = "specific"

    # Check for 'max' or 'min' in the query
    max_temp = "max" in user_input.lower()
    min_temp = "min" in user_input.lower()

    # Extract specific date if mentioned
    for ent in doc.ents:
        if ent.label_ == "DATE":
            parsed_date, parsed = try_parse_date(ent.text)
            if parsed:
                specific_date = parsed_date
                break

    # Print the extracted details
    print(f"City Name: {city_name}, Time Frame: {time_frame}, Specific Date: {specific_date}, Max Temp: {max_temp},"
          f" Min Temp: {min_temp}")

    return city_name, time_frame, specific_date, max_temp, min_temp


# Function to parse date
def try_parse_date(date_str):
    try:
        # First try to parse the date using dateutil's parser
        return parse(date_str, fuzzy=True).date(), True
    except ValueError:
        # If it fails, check if it's a weekday and calculate the next occurrence
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        date_str = date_str.lower()
        if date_str in weekdays:
            return get_date_for_weekday(date_str), True
    return None, False


# Function to get the date for a specific weekday
def get_date_for_weekday(weekday_str):
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    today_weekday = datetime.today().weekday()
    target_weekday = weekdays.index(weekday_str.lower())

    # Calculate the number of days to add
    days_ahead = target_weekday - today_weekday
    if days_ahead <= 0:
        days_ahead += 7

    target_date = datetime.today() + timedelta(days=days_ahead)
    return target_date.date()


# Function to get coordinates for a city
def get_coordinates_for_city(city_name, open_weather_api_key):
    geocoding_url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {"q": city_name, "limit": 1, "appid": open_weather_api_key}
    response = requests.get(geocoding_url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data:
            return data[0]["lat"], data[0]["lon"]
    return None, None


# Function to map weather code to condition
def map_weather_code_to_condition(weather_code):
    weather_conditions = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing grime fog",
        51: "Drizzling Lightly",
        53: "Drizzling Moderately",
        55: "Drizzle heavily",
        56: "Freezing Drizzle with a light intensity",
        57: "Freezing Drizzle with a heavy intensity",
        61: "Light Rain",
        63: "Moderate Rain",
        65: "Heavy Rain",
        66: "Freezing Rain with light intensity",
        67: "Freezing Rain with heavy intensity",
        71: "Snow fall with light intensity",
        73: "Snow fall with moderate intensity",
        75: "Snow fall with heavy intensity",
        77: "Snow grains",
        80: "Rain showers with light intensity",
        81: "Rain showers with moderate intensity",
        82: "Rain showers with violent intensity",
        85: "Snow showers with light intensity",
        86: "Snow showers with heavy intensity",
        95: "Light to moderate thunderstorms",
        96: "Thunderstorms with light hail",
        99: "Thunderstorms with heavy hail"
    }
    return weather_conditions.get(weather_code, "Unknown")


# Function to process weather data based on time frame
def process_weather_data(weather_data, time_text, specific_date=None, max_or_min=None):
    if time_text == "current" and 'current' in weather_data:
        # Process current weather
        current_data = weather_data['current']
        condition = map_weather_code_to_condition(current_data['weather_code'])
        temperature = current_data.get('temperature_2m', "No temperature data")
        return f"Current weather: {condition}, with a temperature of {temperature}°C."

    elif time_text == "hourly" and 'hourly' in weather_data:
        # Process hourly weather
        hourly_data = weather_data['hourly']
        first_hour = hourly_data['time'][0]
        condition = map_weather_code_to_condition(hourly_data['weather_code'][0])
        temperature = hourly_data['temperature_2m'][0]
        return f"Hourly weather for {first_hour}: {condition}, with a temperature of {temperature}°C."

    elif 'daily' in weather_data:
        # Process daily, tomorrow, week, specific date weather
        forecasts = []
        for i, date_str in enumerate(weather_data['daily']['time']):
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            if specific_date and date == specific_date:
                # Specific date
                forecasts.append(format_forecast(weather_data['daily'], i, date_str))
            elif time_text == "tomorrow" and date == datetime.today().date() + timedelta(days=1):
                print(f"Processing 'tomorrow' weather data: {forecasts}")
                # Tomorrow
                forecasts.append(format_forecast(weather_data['daily'], i, date_str))
            elif time_text == "week" and datetime.today().date() <= date <= datetime.today().date() + timedelta(days=7):
                # Week
                forecasts.append(format_forecast(weather_data['daily'], i, date_str))

        return "\n".join(forecasts) if forecasts else "No data for selected timeframe."

    if max_or_min and specific_date:
        daily_data = weather_data.get('daily', [])
        for day_data in daily_data:
            date = datetime.strptime(day_data['time'], '%Y-%m-%d').date()
            if date == specific_date:
                temperature = day_data[f'temperature_2m_{max_or_min}']
                return temperature
    else:
        return "Unknown timeframe or missing data."


# Helper function to format a single forecast entry
def format_forecast(daily_data, index, date_str):
    condition = map_weather_code_to_condition(daily_data['weather_code'][index])
    max_temp = daily_data['temperature_2m_max'][index]
    min_temp = daily_data['temperature_2m_min'][index]
    formatted_forecast = f"{date_str}: {condition}, high of {max_temp}, low of {min_temp}"
    return formatted_forecast


# Helper function to validate date format
def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


# Function to process weather data based on time frame
def process_time_frame_weather(daily_data, time_frame, specific_date=None):
    if not daily_data or 'time' not in daily_data:
        return "Unknown", "No data"

    forecasts = []
    for i, date_str in enumerate(daily_data['time']):
        date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Process data for 'specific_date', 'tomorrow', and 'week'
        if (specific_date and date == specific_date) or \
           (time_frame == "tomorrow" and date == datetime.today().date() + timedelta(days=1)) or \
           (time_frame == "week" and datetime.today().date() <= date <= datetime.today().date() + timedelta(days=7)):

            condition = map_weather_code_to_condition(daily_data['weather_code'][i])
            max_temp = daily_data['temperature_2m_max'][i]
            min_temp = daily_data['temperature_2m_min'][i]
            forecast = f"{date_str}: {condition}, high of {max_temp}, low of {min_temp}"
            forecasts.append(forecast)

    return forecasts


def format_date_conversationally(date_str):
    # Convert the string to a datetime object
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    # Format the date in a more conversational style
    return date_obj.strftime('%A, %B %d, %Y')


# Function to format the weather response to a range of timeframes
def format_weather_response(weather_data, city_name, time_text, specific_date=None, max_temp=False, min_temp=False):
    # Formatting for max or min temperature
    if max_temp or min_temp:
        temp_type = "maximum" if max_temp else "minimum"
        date_str = specific_date.strftime('%Y-%m-%d') if specific_date else "currently"
        if isinstance(weather_data, (int, float)):  # Check if weather_data is just a temperature value
            return f"The {temp_type} temperature in {city_name} for {date_str} is {weather_data}°C."
        else:
            return "Temperature data not available."

    if weather_data is None:
        return "Sorry, I couldn't find any weather data for that location."

        # Formatting for current weather
    elif time_text == "current":
        condition, temperature, precipitation, weather_code = weather_data
        response = f"The current weather in {city_name} is {condition} with a temperature of {temperature}°C."

        # Formatting for hourly weather
    elif time_text == "hourly":
        condition, temperature = weather_data
        response = f"The hourly weather forecast for {city_name} is {condition}, with a temperature of {temperature}°C."

        # Formatting for daily weather
    elif time_text == "daily":
        response = f"The daily weather forecast for {city_name} is {weather_data}"

        # Formatting for tomorrow's weather
    elif time_text == "tomorrow":
        # Extracting the different parts of the forecast
        parts = weather_data.split(': ', 1)[1].split(', ') if ": " in weather_data else [weather_data]
        condition = parts[0]
        high_temp = parts[1].split(' ', 2)[-1]
        low_temp = parts[2].split(' ', 2)[-1]
        response = (f"The weather forecast for tomorrow in {city_name} is {condition} with a high of {high_temp}°C"
                    f" and a low of {low_temp}°C.")

    # Formatting for weekly weather
    elif time_text == "week":
        response = f"The forecast for the next week in {city_name} is {weather_data}"

        # Formatting for a specific date
    elif time_text == "specific":
        # Split the weather_data to get the condition, high, and low temperatures
        if ": " in weather_data:
            date, forecast = weather_data.split(': ', 1)
            parts = forecast.split(', ')
            condition = parts[0]
            high_temp = parts[1].split(' ')[-1]
            low_temp = parts[2].split(' ')[-1]
            # Convert date to conversational format
            formatted_date = format_date_conversationally(date)
            response = (f"The weather forecast for {formatted_date} in {city_name} is {condition} with a high of"
                        f" {high_temp}°C and a low of {low_temp}°C.")

        else:
            # Fallback in case the format is unexpected
            response = f"The weather forecast for {weather_data} in {city_name} is not available."

    else:
        response = "Sorry, I couldn't find any weather data for that location."

    print(f"Final response: {response}")  # Debugging print
    return response


# Function to check if the user is asking for clothing advice
def is_clothing_advice_query(user_input):
    doc = nlp(user_input)
    # Add more keywords as needed
    clothing_keywords = ["wear", "clothing", "dress", "outfit"]
    return any(word in doc.text.lower() for word in clothing_keywords)


# Clothing advice function
def what_to_wear(temperature, precipitation):
    # Basic advice based on temperature and precipitation
    if precipitation > 0:
        rain_gear = "Don't forget to carry an umbrella or wear a raincoat."
    else:
        rain_gear = "No rain expected, so no need for an umbrella."
    if temperature < 0:
        return f"It's freezing! Wear a heavy coat and warm clothing. {rain_gear}"
    elif 0 <= temperature < 10:
        return f"It's cold! Be sure to wear a jacket. {rain_gear}"
    elif 10 <= temperature < 20:
        return f"It's cool. A long sleeve shirt and a light jacket would be a good idea. {rain_gear}"
    elif 20 <= temperature < 30:
        return f"It's warm. A t-shirt or a short-sleeve shirt will do. {rain_gear}"
    else:
        return f"It's hot! Shorts,  a t-shirt and lots of sunscreen are recommended. {rain_gear}"


# Function to get weather data
def get_weather_v3(city_name, time_text, specific_date=None, max_temp=False, min_temp=False):
    open_weather_api_key = os.environ.get('open_weather_api_key')
    lat, lon = get_coordinates_for_city(city_name, open_weather_api_key)
    if lat is None or lon is None:
        return None

    # API call to get weather data
    base_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,"
        f"weather_code&hourly=temperature_2m,precipitation,weather_code&daily=weather_code,"
        f"temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto")

    response = requests.get(base_url)

    if response.status_code == 200:
        weather_data = response.json()

        # Process weather data based on time frame
        if time_text == "current":
            current_data = weather_data['current']
            condition = map_weather_code_to_condition(current_data['weather_code'])
            temperature = current_data.get('temperature_2m')
            precipitation = current_data.get('precipitation')
            weather_code = current_data.get('weather_code')
            return condition, temperature, precipitation, weather_code

        # Process hourly weather
        elif time_text == "hourly":
            hourly_data = weather_data['hourly']
            condition = map_weather_code_to_condition(hourly_data['weather_code'][0])
            temperature = hourly_data['temperature_2m'][0]
            return condition, temperature

        # Process daily weather
        elif time_text == "daily":
            daily_data = weather_data['daily']
            forecasts = process_time_frame_weather(daily_data, time_text)
            return "\n".join(forecasts) if forecasts else "No data for selected timeframe."

        # Process tomorrow's weather
        elif time_text == "tomorrow":
            daily_data = weather_data['daily']
            forecasts = process_time_frame_weather(daily_data, time_text)
            return "\n".join(forecasts) if forecasts else "No data for selected timeframe."

        # Process weekly weather
        elif time_text == "week":
            daily_data = weather_data['daily']
            forecasts = process_time_frame_weather(daily_data, time_text)
            return "\n".join(forecasts) if forecasts else "No data for selected timeframe."

        # Process specific date weather
        elif time_text == "specific":
            daily_data = weather_data['daily']
            forecasts = process_time_frame_weather(daily_data, time_text, specific_date)
            return "\n".join(forecasts) if forecasts else "No data for selected timeframe."

        # Process max or min temperature
        if max_temp or min_temp:
            temp_key = 'temperature_2m_max' if max_temp else 'temperature_2m_min'
            daily_data = weather_data.get('daily', [])
            for day_data in daily_data:
                date = datetime.strptime(day_data['time'], '%Y-%m-%d').date()
                if date == specific_date:
                    return day_data[temp_key]
            return "Temperature data not available for the specified date."

        else:
            return "Unknown timeframe or missing data."

    else:
        return None


# Function to get the chatbot response
def get_chatbot_response(user_input):
    # Check if the user input is empty
    if not user_input:
        return "Please enter a message."

    try:
        # Retrieve the last queried city if available
        city_name = session.get('last_city_queried', None)

        # Extract new query details
        new_city_name, time_frame, specific_date, max_temp, min_temp = extract_weather_query_details(user_input)

        # Update city name if a new one is provided
        if new_city_name:
            city_name = new_city_name
            session['last_city_queried'] = city_name

        # Check if the query is asking for clothing advice
        if is_clothing_advice_query(user_input) and city_name:
            # Process clothing advice query
            weather_data = get_weather_v3(city_name, "current")
            if weather_data:
                condition, temperature, precipitation, weather_code = weather_data
                return what_to_wear(temperature, precipitation)
            else:
                return "Sorry, I couldn't find current weather data for clothing advice."

        # Handle standard chatbot queries
        elif not is_weather_query(user_input):
            return chatbot.get_response(user_input).text

        # Handle weather-related queries
        else:
            # Process weather query
            weather_data = get_weather_v3(city_name, time_frame, specific_date, max_temp, min_temp)
            if weather_data:
                return format_weather_response(weather_data, city_name, time_frame, specific_date, max_temp, min_temp)
            else:
                return "Sorry, I couldn't find any weather data for that location."

    except Exception as e:
        print(f"Error: {e}")
        return "Sorry, I'm having trouble processing your request right now."


# Function to check if the user input is a weather query
def is_weather_query(user_input):
    return 'weather' in user_input.lower() or any(ent.label_ in ["GPE", "LOC", "DATE"] for ent in nlp(user_input).ents)
