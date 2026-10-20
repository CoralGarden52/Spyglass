from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context
from app.core.config import Settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations() -> None:
    url = Settings().database_url.get_secret_value()
    if context.is_offline_mode():
        context.configure(url=url, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
        with engine.connect() as connection:
            context.configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()


run_migrations()
