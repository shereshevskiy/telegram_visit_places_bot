
class PostgresqlQuery:

    def __init__(self, cols, values=None, table="places", local_bd=False):
        self.cols = cols
        self.values = values
        self.cols_join = ', '.join(cols)
        self.table = table

    def query_select(self):
        pass  # TODO

    def query_insert(self):
        pass  # TODO
