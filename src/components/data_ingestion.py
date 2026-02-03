import os
import sys
from dataclasses import dataclass

import pandas as pd

from src.logger import logging
from src.exception import CustomException

# Import domain logic
from src.data_sources.historical_gas_data import read_combined


@dataclass
class DataIngestionConfig:
    raw_data_path: str = os.path.join("artifacts", "raw_gas_data.csv")
    train_data_path: str = os.path.join("artifacts", "train.csv")
    test_data_path: str = os.path.join("artifacts", "test.csv")
    test_size: float = 0.2
    random_state: int = 42


class DataIngestion:
    def __init__(self):
        self.ingestion_config = DataIngestionConfig()

    def initiate_data_ingestion(self):
        logging.info("Started data ingestion for natural gas consumption project")

        try:
            # Read and combine raw data
            logging.info("Reading and combining raw gas-related datasets")
            df = read_combined()

            logging.info(f"Raw dataset shape: {df.shape}")

            os.makedirs(os.path.dirname(self.ingestion_config.raw_data_path), exist_ok=True)

            # Save raw data
            df.to_csv(self.ingestion_config.raw_data_path)
            logging.info("Raw dataset saved successfully")

            # Drop rows with missing target
            df = df.dropna(subset=["consumption"])

            df = df.sort_index()

            split_index = int(len(df) * (1 - self.ingestion_config.test_size))
            train_df = df.iloc[:split_index]
            test_df = df.iloc[split_index:]

            train_df.to_csv(self.ingestion_config.train_data_path)
            test_df.to_csv(self.ingestion_config.test_data_path)

            logging.info("Train-test split completed")
            logging.info("Data ingestion completed successfully")

            return (
                self.ingestion_config.train_data_path,
                self.ingestion_config.test_data_path,
            )

        except Exception as e:
            logging.error("Error occurred during data ingestion")
            raise CustomException(e, sys)