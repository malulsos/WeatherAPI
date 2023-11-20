# WeatherAPI Project

## Description
This project is a Flask-based web application designed to provide real-time weather data. It integrates with Windy.com's Point Forecast API and Map API to display weather information for various locations across England.

## Installation

To set up this project locally, follow these steps:

1. Clone the repository:
`git clone https://github.com/malulsos/WeatherAPI.git`

2. Navigate to the project directory:
`cd WeatherAPI`

3. Install required packages:
`pip install -r requirements.txt`

## Usage

Run the application using Flask:

`flask run`

The application will start, and you can access it via `http://localhost:5000` in your web browser.

## Configuration

The application requires certain environmental variables to function correctly, which are set in a `.env` file. This file is not included in the repository for security reasons and will be provided separately.

### .env File

The `.env` file contains the following variables:

- `POINT_FORCAST_API_KEY`: The API key for Windy.com's Point Forecast API.
- `map_key`: The API key for Windy.com's Map Forecast API.
- `secret_key`: Session key

Make sure to place the `.env` file in the root directory of the project before starting the application.

Author: Julian Hirst
