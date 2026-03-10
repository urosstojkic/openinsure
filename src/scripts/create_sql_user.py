"""Create Azure SQL contained user for the Container App managed identity."""

import struct

import pyodbc
from azure.identity import AzureCliCredential

credential = AzureCliCredential()
token = credential.get_token("https://database.windows.net/.default")
token_bytes = token.token.encode("UTF-16-LE")
token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=openinsure-dev-sql-knshtzbusr734.database.windows.net;"
    "Database=openinsure-db;"
    "Encrypt=yes;TrustServerCertificate=no;"
)
conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct})
conn.autocommit = True
cursor = conn.cursor()

try:
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'openinsure-backend')
        BEGIN
            CREATE USER [openinsure-backend] FROM EXTERNAL PROVIDER;
            ALTER ROLE db_datareader ADD MEMBER [openinsure-backend];
            ALTER ROLE db_datawriter ADD MEMBER [openinsure-backend];
            ALTER ROLE db_ddladmin ADD MEMBER [openinsure-backend];
        END
    """)
    print("SQL user created for openinsure-backend managed identity")
except Exception as e:
    print(f"SQL user creation: {e}")

# Verify
cursor.execute("SELECT name, type_desc FROM sys.database_principals WHERE name = 'openinsure-backend'")
row = cursor.fetchone()
if row:
    print(f"Verified: {row[0]} ({row[1]})")
else:
    print("Warning: user not found after creation")

cursor.close()
conn.close()
print("Done")
