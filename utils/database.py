import psycopg2

class DatabaseUtil:

    def __init__(self,db_config):
        self.db_config = db_config

        try:
            self.connection = psycopg2.connect(**db_config)
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            self.connection = None

    def schema_details(self,schema_name):
        schema_info_context = ""

        connection=self.connection  
        cursor = connection.cursor()

        schema_info_context = f"Database Schema: {schema_name}\n"

        try:
            cursor.execute("SELECT table_name from information_schema.tables where table_schema = %s;",(schema_name,))
            tables_list = cursor.fetchall()

            for table in tables_list:
                table_name = table[0]

                schema_info_context = f"{schema_info_context}\n{table_name}\n"

                cursor.execute("SELECT column_name, data_type from information_schema.columns where table_name = %s;",(table_name,))
                column_list = cursor.fetchall()

                for column in column_list:
                    column_name = column[0]
                    data_type = column[1]
                    schema_info_context = f"{schema_info_context} Column: {column_name} , Data Type:{data_type}\n"

                cursor.execute(f"SELECT * FROM {schema_name}.{table_name} LIMIT 5;")
                sample_data = cursor.fetchall()
                for row in sample_data:
                    schema_info_context = f"{schema_info_context} Sample Data: {row}\n"

            return schema_info_context
        except Exception as e:
            print(f"Error retrieving schema details: {e}")
            schema_info_context = f"Error retrieving schema details: {e}"

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def execute_query(self, query):
        try:
            connection=self.connection  
            cursor = connection.cursor()
            cursor.execute(query)
            result = cursor.fetchall()
            connection.commit()
            return str(result)
        except Exception as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()


obj = DatabaseUtil({
    "host":"localhost",
    "port":5433,
    "user":"postgres",
    "password":"1234",
    "dbname":"postgres"
})
    
result = obj.schema_details("public")

with open("schema_details.txt", "w") as file:
    file.write(result)







    