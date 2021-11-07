from pydantic import BaseModel
from fastapi import FastAPI


class AppConfig(BaseModel):
    max_report_size: int
    max_user_reports: int


def get_app_config(app: FastAPI) -> AppConfig:
    return app.state.config


def set_app_config(app: FastAPI, config: AppConfig) -> None:
    app.state.config = config
