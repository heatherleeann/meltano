import logging
import os
import sqlalchemy
from pathlib import Path
from collections import OrderedDict
from flask import jsonify, redirect, url_for
from pypika import Query, Order

from meltano.core.project import Project
from meltano.api.models import db
from meltano.api.security import create_dev_user
from meltano.core.project import Project
from meltano.core.m5o.m5oc_file import M5ocFile
from meltano.core.sql.analysis_helper import AnalysisHelper
from meltano.core.sql.sql_utils import SqlUtils
from .settings_helper import SettingsHelper


meltano_model_path = Path(os.getcwd(), "model")


class ConnectionNotFound(Exception):
    def __init__(self, connection_name: str):
        self.connection_name = connection_name
        super().__init__("{connection_name} is missing.")


class SqlHelper(SqlUtils):
    def parse_sql(self, input):
        placeholders = self.placeholder_match(input)

    def placeholder_match(self, input):
        outer_pattern = r"(\$\{[\w\.]*\})"
        inner_pattern = r"\$\{([\w\.]*)\}"
        outer_results = re.findall(outer_pattern, input)
        inner_results = re.findall(inner_pattern, input)
        return (outer_results, inner_results)

    def get_m5oc_model(self, model_name):
        m5oc_file = Path(meltano_model_path).joinpath(f"{model_name}.model.m5oc")
        return M5ocFile.load(m5oc_file)

    def get_db_engine(self, connection_name):
        project = Project.find()
        settings_helper = SettingsHelper()
        connections = settings_helper.get_connections()["settings"]["connections"]

        try:
            connection = next(
                connection
                for connection in connections
                if connection["name"] == connection_name
            )

            if connection["dialect"] == "postgresql":
                psql_params = ["username", "password", "host", "port", "database"]
                user, pw, host, port, db = [connection[param] for param in psql_params]
                connection_url = f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}"
            elif connection["dialect"] == "sqlite":
                db_path = project.root.joinpath(connection["path"])
                connection_url = f"sqlite:///{db_path}"

            return sqlalchemy.create_engine(connection_url)

            raise ConnectionNotFound(connection_name)
        except StopIteration:
            raise ConnectionNotFound(connection_name)

    def get_query_results(self, connection_name, sql):
        engine = self.get_db_engine(connection_name)
        results = engine.execute(sql)
        results = [OrderedDict(row) for row in results]
        return results

    def reset_db(self):
        try:
            db.drop_all()
        except sqlalchemy.exc.OperationalError as err:
            logging.error("Failed drop database.")

        db.create_all()
        create_dev_user()
