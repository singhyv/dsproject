import sys
import requests
import pandas as pd

from src.logger import logging
from src.exception import CustomException

ENDPOINT = "https://datenservice.tradinghub.eu/XmlInterface/getXML.ashx?ReportId=AggregatedConsumptionData"


def get_realtime_consumption(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.Series:
    
    if start_date >= end_date:
        raise ValueError("start_date must be earlier than end_date")

    try:
        logging.info("Fetching realtime consumption data")

        response = requests.get(ENDPOINT)
        if response.status_code != 200:
            raise RuntimeError("Consumption API request failed")

        consumption = pd.read_xml(response.content)

        required_columns = [
            "Gasday",
            "HGasSLPsyn",
            "HGasSLPana",
            "LGasSLPsyn",
            "LGasSLPana",
            "HGasRLMmT",
            "LGasRLMmT",
            "HGasRLMoT",
            "LGasRLMoT",
        ]

        consumption = consumption[required_columns].dropna()
        consumption["Gasday"] = pd.to_datetime(consumption["Gasday"])
        consumption = consumption.set_index("Gasday")

        consumption = consumption[start_date:end_date]

        aggregated = (
            consumption.sum(axis="columns") / 1000
        ).rename("consumption_mwh")

        aggregated = aggregated.sort_index()

        logging.info("Realtime consumption data fetched successfully")
        return aggregated

    except Exception as e:
        logging.error("Error fetching realtime consumption data")
        raise CustomException(e, sys)