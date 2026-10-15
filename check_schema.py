from sqlalchemy import inspect
from sqlmodel import SQLModel
from db import engine
import database.models  # importing registers every table on SQLModel.metadata

inspector = inspect(engine)          # reads the schema from Postgres
existing = set(inspector.get_table_names())

for table in SQLModel.metadata.sorted_tables:   # the schema in the Python code 
    if table.name not in existing:
        print(f"Missing table:  {table.name}")
        continue
    db_cols = {c["name"] for c in inspector.get_columns(table.name)}
    model_cols = {c.name for c in table.columns}
    for col in sorted(model_cols - db_cols):
        print(f"Missing column: {table.name}.{col}")
    for col in sorted(db_cols - model_cols):
        print(f"Extra column:   {table.name}.{col}  (in DB, not in python model)")

print("Done.")