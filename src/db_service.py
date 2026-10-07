"""Persist transformed bird observations in Cassandra."""

import os
import re
from datetime import date, datetime
from typing import Any

import pandas as pd
from cassandra.cluster import Cluster
from dotenv import load_dotenv

load_dotenv()


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


CASSANDRA_HOST = required_env("CASSANDRA_HOST")
CASSANDRA_PORT = int(required_env("CASSANDRA_PORT"))
CASSANDRA_KEYSPACE = required_env("CASSANDRA_KEYSPACE")
CASSANDRA_TABLE = required_env("CASSANDRA_TABLE")
CASSANDRA_BY_DATE_TABLE = required_env("CASSANDRA_BY_DATE_TABLE")
CASSANDRA_BY_SPECIES_TABLE = required_env("CASSANDRA_BY_SPECIES_TABLE")
CASSANDRA_BY_SPECIES_DATE_TABLE = required_env("CASSANDRA_BY_SPECIES_DATE_TABLE")
CASSANDRA_BY_COMMON_NAME_TABLE = required_env("CASSANDRA_BY_COMMON_NAME_TABLE")
CASSANDRA_REPLICATION_FACTOR = int(required_env("CASSANDRA_REPLICATION_FACTOR"))

for setting_name, identifier in (
    ("CASSANDRA_KEYSPACE", CASSANDRA_KEYSPACE),
    ("CASSANDRA_TABLE", CASSANDRA_TABLE),
    ("CASSANDRA_BY_DATE_TABLE", CASSANDRA_BY_DATE_TABLE),
    ("CASSANDRA_BY_SPECIES_TABLE", CASSANDRA_BY_SPECIES_TABLE),
    ("CASSANDRA_BY_SPECIES_DATE_TABLE", CASSANDRA_BY_SPECIES_DATE_TABLE),
    ("CASSANDRA_BY_COMMON_NAME_TABLE", CASSANDRA_BY_COMMON_NAME_TABLE),
):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", identifier):
        raise RuntimeError(f"{setting_name} must be a valid CQL identifier")


def _cql_date(value: Any) -> date | None:
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def insert_data(df: pd.DataFrame) -> int:
    """Upsert a DataFrame of bird observations and return rows written."""
    if df.empty:
        return 0

    required_columns = {
        "observation_id",
        "common_name",
        "scientific_name",
        "observed_on",
        "latitude",
        "longitude",
    }
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(f"DataFrame is missing required columns: {sorted(missing_columns)}")

    cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
    written = 0
    try:
        session = cluster.connect()
        replication = (
            "{'class': 'SimpleStrategy', "
            f"'replication_factor': {CASSANDRA_REPLICATION_FACTOR}" + "}"
        )
        session.execute(
            f"CREATE KEYSPACE IF NOT EXISTS {CASSANDRA_KEYSPACE} "
            f"WITH replication = {replication}"
        )
        session.set_keyspace(CASSANDRA_KEYSPACE)
        session.execute(
            f"CREATE TABLE IF NOT EXISTS {CASSANDRA_TABLE} ("
            "observation_id bigint PRIMARY KEY, "
            "common_name text, "
            "scientific_name text, "
            "observed_on date, "
            "latitude double, "
            "longitude double)"
        )
        session.execute(
            f"CREATE TABLE IF NOT EXISTS {CASSANDRA_BY_DATE_TABLE} ("
            "observed_on date, "
            "observation_id bigint, "
            "common_name text, "
            "scientific_name text, "
            "latitude double, "
            "longitude double, "
            "PRIMARY KEY ((observed_on), observation_id))"
        )
        session.execute(
            f"CREATE TABLE IF NOT EXISTS {CASSANDRA_BY_SPECIES_TABLE} ("
            "scientific_name text, "
            "observed_on date, "
            "observation_id bigint, "
            "common_name text, "
            "latitude double, "
            "longitude double, "
            "PRIMARY KEY ((scientific_name), observed_on, observation_id)) "
            "WITH CLUSTERING ORDER BY (observed_on DESC, observation_id ASC)"
        )
        session.execute(
            f"CREATE TABLE IF NOT EXISTS {CASSANDRA_BY_SPECIES_DATE_TABLE} ("
            "scientific_name text, "
            "observed_on date, "
            "observation_id bigint, "
            "common_name text, "
            "latitude double, "
            "longitude double, "
            "PRIMARY KEY ((scientific_name, observed_on), observation_id))"
        )
        session.execute(
            f"CREATE TABLE IF NOT EXISTS {CASSANDRA_BY_COMMON_NAME_TABLE} ("
            "common_name text, "
            "observed_on date, "
            "observation_id bigint, "
            "scientific_name text, "
            "latitude double, "
            "longitude double, "
            "PRIMARY KEY ((common_name), observed_on, observation_id)) "
            "WITH CLUSTERING ORDER BY (observed_on DESC, observation_id ASC)"
        )
        observation_statement = session.prepare(
            f"INSERT INTO {CASSANDRA_TABLE} "
            "(observation_id, common_name, scientific_name, observed_on, latitude, longitude) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )
        date_statement = session.prepare(
            f"INSERT INTO {CASSANDRA_BY_DATE_TABLE} "
            "(observed_on, observation_id, common_name, scientific_name, latitude, longitude) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )
        species_statement = session.prepare(
            f"INSERT INTO {CASSANDRA_BY_SPECIES_TABLE} "
            "(scientific_name, observed_on, observation_id, common_name, latitude, longitude) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )
        species_date_statement = session.prepare(
            f"INSERT INTO {CASSANDRA_BY_SPECIES_DATE_TABLE} "
            "(scientific_name, observed_on, observation_id, common_name, latitude, longitude) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )
        common_name_statement = session.prepare(
            f"INSERT INTO {CASSANDRA_BY_COMMON_NAME_TABLE} "
            "(common_name, observed_on, observation_id, scientific_name, latitude, longitude) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )

        for row in df.to_dict(orient="records"):
            observation_id = row["observation_id"]
            if pd.isna(observation_id):
                continue

            cql_observation_id = int(observation_id)
            common_name = None if pd.isna(row["common_name"]) else str(row["common_name"])
            scientific_name = (
                None if pd.isna(row["scientific_name"]) else str(row["scientific_name"])
            )
            observed_on = _cql_date(row["observed_on"])
            latitude = None if pd.isna(row["latitude"]) else float(row["latitude"])
            longitude = None if pd.isna(row["longitude"]) else float(row["longitude"])

            session.execute(
                observation_statement,
                (
                    cql_observation_id,
                    common_name,
                    scientific_name,
                    observed_on,
                    latitude,
                    longitude,
                ),
            )
            if observed_on is not None:
                session.execute(
                    date_statement,
                    (
                        observed_on,
                        cql_observation_id,
                        common_name,
                        scientific_name,
                        latitude,
                        longitude,
                    ),
                )
                if scientific_name is not None:
                    session.execute(
                        species_statement,
                        (
                            scientific_name,
                            observed_on,
                            cql_observation_id,
                            common_name,
                            latitude,
                            longitude,
                        ),
                    )
                    session.execute(
                        species_date_statement,
                        (
                            scientific_name,
                            observed_on,
                            cql_observation_id,
                            common_name,
                            latitude,
                            longitude,
                        ),
                    )
                if common_name is not None:
                    session.execute(
                        common_name_statement,
                        (
                            common_name,
                            observed_on,
                            cql_observation_id,
                            scientific_name,
                            latitude,
                            longitude,
                        ),
                    )
            written += 1
    finally:
        cluster.shutdown()

    return written