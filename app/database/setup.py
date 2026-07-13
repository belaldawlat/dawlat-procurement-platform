from database.connection import get_connection


def create_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                category TEXT NOT NULL,
                country TEXT NOT NULL,
                contact_name TEXT,
                email TEXT,
                phone TEXT,
                website TEXT,
                notes TEXT
            )
            """
        )


if __name__ == "__main__":
    create_database()
    print("✅ Database created successfully.")
