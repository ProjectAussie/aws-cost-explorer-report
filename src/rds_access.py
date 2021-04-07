import json
from typing import List, Mapping, Sequence, Union

import boto3
import pandas as pd
import psycopg2
from psycopg2.extensions import connection


def get_config():

    client = boto3.client("secretsmanager")
    secrets = client.get_secret_value(SecretId="prod-db-main")
    secrets_dict = json.loads(secrets["SecretString"])
    return secrets_dict


def get_connection() -> connection:
    secrets_dict = get_config()
    username = secrets_dict["username"]
    password = secrets_dict["password"]
    host = secrets_dict["host"]
    dbname = secrets_dict["dbname"]
    conn = psycopg2.connect(dbname=dbname, user=username, password=password, host=host)
    return conn


def run_query(
    sql: str,
    substitutions: Union[Sequence, Mapping] = None,
    read_only: bool = True,
) -> List:

    real_connection = get_connection()
    if read_only:
        real_connection.set_session(readonly=True)
    cursor = real_connection.cursor()
    cursor.execute(sql, substitutions)
    rows = cursor.fetchall()
    cursor.close()
    real_connection.commit()
    return rows


def get_dogs_per_day():
    query = """
    WITH dogs_per_tranche AS 
(
    SELECT latest_tranche_date, count(*) AS dogs_in_delivery FROM genotypes WHERE latest_tranche_date IS NOT NULL GROUP BY latest_tranche_date
)
SELECT
    illumina_delivery
    , extract(epoch FROM pipeline_completed_at - pipeline_started_at)/(60*60) AS pipeline_runtime_hrs
    , 12 AS target
    , d.dogs_in_delivery AS num_dogs
FROM pipeline_status p
LEFT JOIN dogs_per_tranche d
ON p.tranche_date = d.latest_tranche_date
WHERE NOW() - delivery_uploaded_to_s3_at < '10 days'
ORDER BY pipeline_started_at asc
    """

    records = run_query(query)
    df = pd.DataFrame.from_records(
        records, columns=["delivery_id", "runtime", "target", "n_dogs"]
    )
    df["date"] = df["delivery_id"].str.split("_", expand=True)[1]
    df = df.sort_values("date", ascending=True)
    sliced_df = df.iloc[-10:, 3:]
    sliced_df.dropna(inplace=True)
    dogs_per_day = sliced_df.set_index("date", drop=True)
    dogs_per_day.loc["total", "n_dogs"] = sum(dogs_per_day["n_dogs"])
    return dogs_per_day
