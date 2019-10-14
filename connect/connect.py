import psycopg2
from psycopg2 import Error
import configparser
import os


def connect_to_db(local_db=False):
    """
    Connect to PostgreSQL db, heroku or local, depending from local_db (False or True)

    :param local_db: bool, default is True. Whether will be the connect to test database or real database
    :return:
    """
    path_to_connect_config = os.path.dirname(os.path.abspath(__file__))
    config = configparser.ConfigParser()
    config.read(os.path.join(path_to_connect_config, 'connect.cfg'))
    db_type = "LOCAL" if local_db else "HEROKU"

    print(f"Connecting to {db_type} PostgeSQL database...")
    try:
        connect = psycopg2.connect(**config[db_type])
        print("Connection established.")
        return connect
    except Error as err:
        print("ERROR:", err)
        print("Connection failed: the connection not happened")


if __name__ == '__main__':
    conn = None
    try:
        conn = connect_to_db()
    except Error as e:
        print("ERROR:", e)
    finally:
        if conn:
            conn.close()
            print("Same connection test is OK")
            print("Connection closed")
        else:
            print("NOTE: The connection not happened")
