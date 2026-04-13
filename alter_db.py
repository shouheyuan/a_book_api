import sys
import os

from app.db import engine
from sqlalchemy import text

with engine.connect() as con:
    try:
        con.execute(text("ALTER TABLE user_profiles ADD COLUMN age VARCHAR(50);"))
        print("Added age")
    except Exception as e:
        print("Error adding age:", e)

    try:
        con.execute(text("ALTER TABLE user_profiles ADD COLUMN preferences TEXT;"))
        print("Added preferences")
    except Exception as e:
        print("Error adding preferences:", e)

    con.commit()
print("Done")
