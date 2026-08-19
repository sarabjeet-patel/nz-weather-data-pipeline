from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import requests
import psycopg2
import os


# Retrieve API key from environment variable (set via Docker Compose)
API_KEY = os.getenv("OPENWEATHER_API_KEY")

# List of major NZ cities with coordinates for accurate weather data
NZ_CITIES = [
    {"name": "Auckland", "lat": -36.8492, "lon": 174.7653},
    {"name": "Wellington", "lat": -41.2889, "lon": 174.7772},
    {"name": "Christchurch", "lat": -43.5311, "lon": 172.6361},
    {"name": "Hamilton", "lat": -37.7833, "lon": 175.2833},
    {"name": "Tauranga", "lat": -37.6860, "lon": 176.1670},
    {"name": "Dunedin", "lat": -45.8742, "lon": 170.5036},
    {"name": "Palmerston North", "lat": -40.3564, "lon": 175.6111},
    {"name": "Napier", "lat": -39.4926, "lon": 176.9123},
    {"name": "Nelson", "lat": -41.2706, "lon": 173.2840},
    {"name": "New Plymouth", "lat": -39.0667, "lon": 174.0833}
]


# Function to fetch current weather data from OpenWeatherMap
def fetch_weather(lat, lon, city_name):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    response = requests.get(url)
    data = response.json()
    weather = {
        "city": city_name,
        "temperature": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "description": data["weather"][0]["description"],
        "date": datetime.utcnow().date()
    }
    return weather


# Function to connect to PostgreSQL and store weather data
def store_weather():
    import logging

    # Connect to PostgreSQL container (host is service name in Docker Compose)
    conn = psycopg2.connect(
        host="postgres",
        database= os.getenv("POSTGRES_DB"),
        user= os.getenv("POSTGRES_USER"),
        password= os.getenv("POSTGRES_PASSWORD")
    )
    cur = conn.cursor()

    for city in NZ_CITIES:
        try:
            # Fetch and log weather data
            weather = fetch_weather(city["lat"], city["lon"], city["name"])
            logging.info(f"Fetched weather for {city['name']}: {weather}")

            # Insert weather data into the weather table
            insert_query = """
            INSERT INTO weather (city, temperature, humidity, weather_description, date)
            VALUES (%s, %s, %s, %s, %s)
            """
            cur.execute(insert_query, (
                weather["city"],
                weather["temperature"],
                weather["humidity"],
                weather["description"],
                weather["date"]
            ))

            logging.info(f"Inserted weather for {city['name']} successfully.")
        except Exception as e:
            logging.error(f"Error with {city['name']}: {e}")

    conn.commit()
    cur.close()
    conn.close()


# Define Airflow DAG
default_args = {
    "start_date": datetime(2024, 1, 1),
}

# DAG definition: runs daily and triggers weather fetch/store task
with DAG(
    dag_id="weather_etl",
    schedule_interval="@daily",
    default_args=default_args,
    catchup=False
) as dag:
    
    store_weather_task = PythonOperator(
        task_id="store_weather",
        python_callable=store_weather
    )

    store_weather_task