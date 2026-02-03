import os
import sys
import pandas as pd

from src.logger import logging
from src.exception import CustomException


class HistoricalGasData:
    def __init__(self, raw_data_dir: str = "data/raw"):
        self.raw_data_dir = raw_data_dir

    def read_temperatures(self) -> pd.Series:
        try:
            logging.info("Reading historical temperature data")

            temperature_file = os.path.join(
                self.raw_data_dir,
                "H_ERA5_ECMW_T639_TA-_0002m_Euro_NUT0_S197901010000_E202212312300_INS_TIM_01d_NA-_noc_org_NA_NA---_NA---_NA---.csv",
            )

            temperatures_raw = pd.read_csv(
                temperature_file,
                header=52,
                index_col=0,
                parse_dates=True,
            )

            # Convert Kelvin to Celsius
            temperatures = (
                temperatures_raw["DE"] - 273.15
            ).rename("temperature")

            temperatures = temperatures.sort_index()

            logging.info("Temperature data loaded successfully")
            return temperatures

        except Exception as e:
            logging.error("Error while reading temperature data")
            raise CustomException(e, sys)
        
    def read_imbalance_prices(self) -> pd.Series:
        try:
            logging.info("Reading historical gas imbalance prices")

            # -------- NetConnect (XML) --------
            netconnect_file = os.path.join(
                self.raw_data_dir,
                "NetConnect Germany imbalance prices.xml",
            )

            netconnect_raw = pd.read_xml(netconnect_file)
            netconnect = netconnect_raw.loc[
                netconnect_raw["Gasday"].notna()
            ].set_index("Gasday")[1:]

            netconnect.index = pd.to_datetime(netconnect.index)
            netconnect.index.name = "Date"

            netconnect_prices = netconnect[
                "NegativeEnergyImbalanceFee"
            ].astype(float)

            # -------- GASPOOL (CSV) --------
            gaspool_file = os.path.join(
                self.raw_data_dir,
                "GASPOOL imbalance prices.csv",
            )

            gaspool_raw = pd.read_csv(
                gaspool_file, sep=";", index_col="Date"
            )

            gaspool = gaspool_raw[84:]
            gaspool.index = pd.to_datetime(
                gaspool.index, format="%d.%m.%Y"
            )

            gaspool_prices = gaspool[
                "Price for pos. compensation energy [Eurocent/kWh]"
            ].astype(float)

            # -------- Trading Hub Europe (CSV) --------
            the_file = os.path.join(
                self.raw_data_dir,
                "Trading Hub Europe imbalance prices.csv",
            )

            the_raw = pd.read_csv(
                the_file, sep=";", index_col="Gastag", decimal=","
            )

            the_raw.index = pd.to_datetime(
                the_raw.index, format="%d.%m.%Y"
            )

            the_prices = the_raw[
                "Positiver Ausgleichsenergiepreis (EUR/MWh)"
            ].astype(float)

            # -------- Combine --------
            combined_prices = pd.concat(
                [
                    (netconnect_prices + gaspool_prices).dropna() / 2,
                    the_prices,
                ]
            ).rename("imbalance_prices")

            combined_prices = combined_prices.sort_index()

            logging.info("Imbalance price data loaded successfully")
            return combined_prices

        except Exception as e:
            logging.error("Error while reading imbalance prices")
            raise CustomException(e, sys)
        
    def read_crude_oil_prices(self) -> pd.Series:
        try:
            logging.info("Reading historical crude oil prices (Brent - Europe)")

            crude_oil_file = os.path.join(
                self.raw_data_dir,
                "Crude oil prices Brent - Europe.csv",
            )

            crude_oil_raw = pd.read_csv(
                crude_oil_file,
                parse_dates=["DATE"],
                index_col="DATE",
                decimal=".",
            )

            crude_oil_raw.index.name = "Date"

            # Convert values to float where possible
            crude_oil_raw = crude_oil_raw.applymap(
                lambda x: float(x) if isinstance(x, str) and x.replace(".", "", 1).isdigit() else float(x)
            )

            prices = (
                crude_oil_raw["DCOILBRENTEU"]
                .rename("crude_oil_price")
                .sort_index()
            )

            # Fill missing dates
            prices = prices.reindex(
                pd.date_range(
                    start=prices.index.min(),
                    end=prices.index.max(),
                    freq="D",
                )
            )

            # Interpolate missing values
            prices = prices.interpolate()

            logging.info("Crude oil price data loaded successfully")
            return prices

        except Exception as e:
            logging.error("Error while reading crude oil prices")
            raise CustomException(e, sys)
        
    def read_electricity_prices(self) -> pd.Series:
        try:
            logging.info("Reading historical electricity prices")

            electricity_file = os.path.join(
                self.raw_data_dir,
                "European wholesale electricity prices.csv",
            )

            electricity_raw = pd.read_csv(electricity_file)

            # Filter for Germany
            electricity_germany = electricity_raw.loc[
                electricity_raw["ISO3 Code"] == "DEU"
            ]

            electricity_germany = electricity_germany.set_index("Date")
            electricity_germany.index = pd.to_datetime(electricity_germany.index)

            electricity_prices = (
                electricity_germany["Price (EUR/MWhe)"]
                .astype(float)
                .rename("electricity_price")
                .sort_index()
            )

            logging.info("Electricity price data loaded successfully")
            return electricity_prices

        except Exception as e:
            logging.error("Error while reading electricity prices")
            raise CustomException(e, sys)
        
    def read_eua_auctions(self) -> pd.Series:
        try:
            logging.info("Reading historical EUA auction prices")

            base_dir = os.path.join(self.raw_data_dir, "EEX EUA Auctions")

            files_style_1 = [
                "emission-spot-primary-market-auction-report-2012-data.xls",
                "emission-spot-primary-market-auction-report-2013-data.xls",
                "emission-spot-primary-market-auction-report-2014-data.xls",
                "emission-spot-primary-market-auction-report-2015-data.xls",
            ]

            files_style_2 = [
                "emission-spot-primary-market-auction-report-2016-data.xls",
            ]

            files_style_3 = [
                "emission-spot-primary-market-auction-report-2017-data.xls",
                "emission-spot-primary-market-auction-report-2018-data.xls",
                "emission-spot-primary-market-auction-report-2019-data.xls",
                "emission-spot-primary-market-auction-report-2020-data.xlsx",
                "emission-spot-primary-market-auction-report-2021-data.xlsx",
                "emission-spot-primary-market-auction-report-2022-data.xlsx",
                "primary_auction_report_20230214_39969994.xlsx",
            ]

            eua_prices = pd.Series(dtype="float64")

            # Style 1
            for file in files_style_1:
                path = os.path.join(base_dir, file)
                data = pd.read_excel(
                    path,
                    header=2,
                    index_col="Date",
                    parse_dates=True,
                )["Auction Price €/tCO2"]

                eua_prices = pd.concat([eua_prices, data])

            # Style 2
            for file in files_style_2:
                path = os.path.join(base_dir, file)
                data = pd.read_excel(
                    path,
                    header=2,
                    index_col="Date",
                    parse_dates=True,
                )["Auction Price EUR/tCO2"]

                eua_prices = pd.concat([eua_prices, data])

            # Style 3
            for file in files_style_3:
                path = os.path.join(base_dir, file)
                data = pd.read_excel(
                    path,
                    header=5,
                    index_col="Date",
                    parse_dates=True,
                )["Auction Price €/tCO2"]

                eua_prices = pd.concat([eua_prices, data])

            # Clean & align
            eua_prices = (
                eua_prices.sort_index()
                .groupby(eua_prices.index)
                .mean()
                .rename("eua_price")
            )

            # Fill missing dates
            eua_prices = eua_prices.reindex(
                pd.date_range(
                    start=eua_prices.index.min(),
                    end=eua_prices.index.max(),
                    freq="D",
                )
            )

            # Interpolate missing values
            eua_prices = eua_prices.interpolate()

            logging.info("EUA auction price data loaded successfully")
            return eua_prices

        except Exception as e:
            logging.error("Error while reading EUA auction prices")
            raise CustomException(e, sys)

    def read_consumption(self) -> pd.Series:
        try:
            logging.info("Reading historical natural gas consumption data")

            ncg_file = os.path.join(
                self.raw_data_dir, "NetConnect Germany natural gas consumption.csv"
            )
            gaspool_file = os.path.join(
                self.raw_data_dir, "GASPOOL natural gas consumption.csv"
            )
            the_file = os.path.join(
                self.raw_data_dir,
                "Trading Hub Europe Publications Transparency Aggregated consumption data.csv",
            )

            # NetConnect
            ncg = pd.read_csv(ncg_file, sep=";", index_col="DayOfUse")
            ncg.index = pd.to_datetime(ncg.index, format="%d.%m.%Y")
            ncg = ncg.select_dtypes("number") / 1000
            ncg = ncg.sum(axis="columns")

            # GASPOOL
            gaspool = pd.read_csv(gaspool_file, sep=";", index_col="Datum")
            gaspool.index = pd.to_datetime(gaspool.index, format="%d.%m.%Y")
            gaspool = gaspool.sum(axis="columns")

            # THE - Trading Hub Europe
            the = pd.read_csv(the_file, sep=";", thousands=",", index_col="Gasday")
            the.index = pd.to_datetime(the.index, format="%d/%m/%Y")
            the = the.select_dtypes("number") / 1000
            the = the.sum(axis="columns")

            consumption = pd.concat(
                [ncg + gaspool, the]
            ).rename("consumption")

            consumption = consumption.sort_index()

            logging.info("Consumption data loaded successfully")
            return consumption

        except Exception as e:
            logging.error("Error while reading consumption data")
            raise CustomException(e, sys)
        

    def read_storage_levels(self) -> pd.Series:
        try:
            logging.info("Reading historical gas storage level data")

            storage_file = os.path.join(
                self.raw_data_dir,
                "StorageData_GIE_2011-01-01_2023-03-02.csv",
            )

            storage_levels = pd.read_csv(
                storage_file,
                sep=";",
                index_col="Gas Day Start",
                parse_dates=True,
                decimal=".",
            )

            storage_levels = (
                storage_levels["Gas in storage (TWh)"]
                .rename("storage_levels")
                .sort_index()
            )

            logging.info("Storage level data loaded successfully")
            return storage_levels

        except Exception as e:
            logging.error("Error while reading storage level data")
            raise CustomException(e, sys)
        
    def read_combined(self) -> pd.DataFrame:
        try:
            logging.info("Combining all historical gas-related datasets")

            # Read individual signals
            consumption = self.read_consumption()
            temperature = self.read_temperatures()
            imbalance_prices = self.read_imbalance_prices()
            electricity_prices = self.read_electricity_prices()
            crude_oil_prices = self.read_crude_oil_prices()
            eua_prices = self.read_eua_auctions()
            storage_levels = self.read_storage_levels()

            # Temperature capped at 18°C (domain logic)
            temperature_capped = temperature.apply(
                lambda x: min(18.0, x)
            ).rename("temperature_capped")

            # Combine into a single DataFrame
            df = pd.concat(
                [
                    temperature.rename("temperature"),
                    temperature_capped,
                    imbalance_prices,
                    electricity_prices,
                    crude_oil_prices,
                    eua_prices,
                    storage_levels,
                    consumption,
                ],
                axis=1,
            )

            # Add weekend feature
            df["weekend"] = (df.index.weekday > 4).astype(float)

            df = df.sort_index()

            logging.info(
                f"Combined dataset created successfully with shape {df.shape}"
            )

            return df

        except Exception as e:
            logging.error("Error while combining historical gas datasets")
            raise CustomException(e, sys)
