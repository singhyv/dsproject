import sys
import requests
import pandas as pd

from src.logger import logging
from src.exception import CustomException

HISTORIC_ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"

CITIES = [
    (52.520008, 13.404954),  # Berlin
    (51.339695, 12.373075),  # Dresden
    (50.937531, 6.960279),   # Cologne
    (48.135125, 11.581981),  # Munich
    (53.551086, 9.993682),   # Hamburg
]


def get_realtime_temperature(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.Series:
    if start_date >= end_date:
        raise ValueError("start_date must be earlier than end_date")
    
    try:
        logging.info("Fetching historical temperature data from Open-Meteo")

        hourly_temperatures = pd.DataFrame()

        for lat, lon in CITIES:
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m",
                "models": "era5_land",
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            }

            response = requests.get(HISTORIC_ENDPOINT, params=params)
            response.raise_for_status()

            data = response.json()

            temps = pd.Series(
                data["hourly"]["temperature_2m"],
                index=pd.to_datetime(data["hourly"]["time"]),
            )

            hourly_temperatures[(lat, lon)] = temps

        hourly_temperatures = hourly_temperatures.mean(axis="columns")
        daily_temperatures = hourly_temperatures.groupby(pd.Grouper(freq="D")).mean()

        daily_temperatures = daily_temperatures.dropna()

        if daily_temperatures.empty:
            last_date = start_date
        else:
            last_date = daily_temperatures.index.max()

        days_missing = (end_date - last_date).days

        if days_missing <= 0:
            return daily_temperatures.rename("temperature").sort_index()
        
        logging.info("Fetching forecast temperature data")

        hourly_forecast = pd.DataFrame()

        for lat, lon in CITIES:
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m",
                "models": "ecmwf_ifs04",
                "past_days": days_missing,
                "forecast_days": 1,
            }

            response = requests.get(FORECAST_ENDPOINT, params=params)
            response.raise_for_status()

            data = response.json()

            temps = pd.Series(
                data["hourly"]["temperature_2m"],
                index=pd.to_datetime(data["hourly"]["time"]),
            )

            hourly_forecast[(lat, lon)] = temps
        
        hourly_forecast = hourly_forecast.mean(axis="columns")
        daily_forecast = hourly_forecast.groupby(pd.Grouper(freq="D")).mean()

        daily_forecast = daily_forecast.iloc[:-1]

        combined = pd.concat(
            [daily_temperatures, daily_forecast]
        ).sort_index()

        logging.info("Realtime temperature data fetched successfully")

        return combined.rename("temperature")

    except Exception as e:
        logging.error("Error fetching realtime temperature data")
        raise CustomException(e, sys)
