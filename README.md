# Transaction-System

Startup:

Starting services:
Start the python venv
source .venv/bin/activate

Start the service
python -m uvicorn services.name_service.app.main:app --reload --port 8001

    Starting db and applying migrations:

    Start psql server:
    sudo service postgresql start

    Check its status:
    sudo service postgresql status

    Sign into psql to see dbs in the server:
    sudo -u postgres psql and \l for listing dbs

    Apply migrations:
    alembic upgrade head (Do this from inside the service folder containing the services alembic init file)

Installing a new package:
pip install ...

Update requirements after installing a new package:
pip freeze > requirements.txt
