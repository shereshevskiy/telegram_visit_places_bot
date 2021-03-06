from psycopg2 import Error

from db.connect import get_connect


class DataBase:

    def __init__(self, cols=("id", "user_id", "name", "address", "photo_id", "lat", "lon"),
                 table="places", local_db=False):
        """

        :param cols:
        :param table:
        :param local_db:
        """
        self.cols = cols
        self.cols_join = ', '.join(cols)
        self.table = table
        self.local_db = local_db

    def query(self, text, query_params=None, commit=False, fetchall=False):
        connect = None
        rows = None
        try:
            connect = get_connect(self.local_db)
            cursor = connect.cursor()
            cursor.execute(text, query_params)
            if commit:
                connect.commit()
            if fetchall:
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

    def query_fetchall(self, text=None, query_params=None):
        return self.query(text, query_params, fetchall=True)

    def query_insert(self, values):
        """

        :param values: tuple of values corresponded with cols
        :return:
        """
        values_templ = ", ".join(["%s"] * len(values))
        cols_join = ', '.join(self.cols[1:])
        text = f"INSERT INTO {self.table} ({cols_join}) VALUES ({values_templ})"
        params = values

        self.query(text, params, commit=True)


if __name__ == '__main__':
    print("Some test for the method .query():")
    psql_query = DataBase()
    # the query to see the tables list from db
    query_text = """SELECT table_name FROM information_schema.tables
                    WHERE table_schema NOT IN ('information_schema','pg_catalog');"""
    print(psql_query.query(query_text, fetchall=True))
