
import mysql.connector
from mysql.connector import Error


def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smart_canteen_db",
            port=3306
        )

        return connection

    except Error as e:
        print("Database connection error:", e)
        return None


# Test database connection
if __name__ == "__main__":

    connection = get_db_connection()

    if connection and connection.is_connected():
        print("================================")
        print("SMART CANTEEN DATABASE CONNECTED")
        print("================================")
        print("MySQL connection successful!")

        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")

        print("\nAvailable Database Tables:")

        for table in cursor.fetchall():
            print("-", table[0])

        cursor.close()
        connection.close()

        print("\nDatabase connection closed.")

    else:
        print("Database connection failed.")
