import time
import pprint
import sys
from typing import List, Dict, Any

import mysql.connector
from mysql.connector import Error as MySQLError
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from config import Config

def get_sql_connection():
    """Cria ligação ao MySQL e devolve o objeto de ligação."""
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        return conn
    except MySQLError as e:
        print("Falha ao ligar ao MySQL:", e, file=sys.stderr)
        raise

def get_mongo_client():
    """Cria ligação ao MongoDB e devolve o cliente."""
    try:
        return MongoClient(Config.build_mongo_uri())
    except PyMongoError as e:
        print("Falha ao ligar ao MongoDB:", e, file=sys.stderr)
        raise


def main():
    print("A confirmar consistência de dados ...")
    conn=get_sql_connection()
    cur = conn.cursor(dictionary=True)
    client=get_mongo_client()
    db=client[Config.MONGO_DB]
    db.book_ratings.delete_many({})
    cur.execute("SELECT user_id, ISBN, book_rating FROM ratings")
    rows = cur.fetchall()

    # para cada ISBN criar estrutura compatível com Mongo
    cache = {}

    for r in rows:
        isbn = r["ISBN"]
        if isbn not in cache:
            cache[isbn] = {"ISBN": isbn, "ratings": []}
        cache[isbn]["ratings"].append({
            "user_id": r["user_id"],
            "book_rating": r["book_rating"]
        })

    for doc in cache.values():
        db.book_ratings.insert_one(doc)
    print("Consistência confirmada.")

    




if __name__ == "__main__":
    main()   