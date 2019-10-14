from psycopg2 import Error

from db.connect import get_connect


class PostgresqlQuery:

    def __init__(self, cols=("user_id", "name", "address", "photo_id", "lat", "lon"), table="places", local_db=False):
        """

        :param cols:
        :param table:
        :param local_db:
        """
        self.cols = cols
        self.cols_join = ', '.join(cols)
        self.table = table
        self.local_db = local_db

    def query(self, query_text, query_params=None):
        connect = None
        try:
            connect = get_connect(self.local_db)
            cursor = connect.cursor()
            cursor.execute(query_text, query_params)

        except Error as e:
            print("ERROR:", e)
        finally:
            if connect:
                connect.close()
                print("Connection closed")
            else:
                print("NOTE: The connection not happened")

    def query_fetchall(self, query_text, query_params=None):
        connect = None
        try:
            connect = get_connect(self.local_db)
            cursor = connect.cursor()
            cursor.execute(query_text, query_params)
            rows = cursor.fetchall()
            return rows

        except Error as e:
            print("ERROR:", e)
        finally:
            if connect:
                connect.close()
                print("Connection closed")
            else:
                print("NOTE: The connection not happened")

    def query_insert(self, values):
        """

        :param values: tuple of values corresponded with cols
        :return:
        """
        connect = None
        try:
            connect = get_connect(self.local_db)
            cursor = connect.cursor()

            values_templ = ", ".join(["%s"] * len(values))
            query_text = f"INSERT INTO {self.table} ({self.cols_join}) VALUES ({values_templ})"
            query_params = values

            cursor.execute(query_text, query_params)
            connect.commit()

        except Error as e:
            print("ERROR:", e)
        finally:
            if connect:
                connect.close()
                print("Connection closed")
            else:
                print("NOTE: The connection not happened")


if __name__ == '__main__':
    print("Some test for the method .query():")
    psql_query = PostgresqlQuery()
    # запрос на просмотра списка таблиц в базе данных
    query_text = """SELECT table_name FROM information_schema.tables
                    WHERE table_schema NOT IN ('information_schema','pg_catalog');"""
    print(psql_query.query(query_text))
