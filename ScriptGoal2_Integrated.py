"""
Grupo 11
Diogo Sousa - 60250; 
Francisco Lopes - 60252;  
Guilherme Almeida - 60264;
Pedro Rosa  - 60294

Script Queries GOAL 2 (MySQL + MongoDB)
------------------------------------------------
Inclui:
  • 3 queries SQL
  • 2 queries MongoDB
  • 2 queries híbridas (reutilizam as anteriores)
"""

import mysql.connector
from mysql.connector import Error as MySQLError
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from typing import List, Dict, Any
import pprint
import sys
from config import Config


# ============================================================
#  FUNÇÕES DE LIGAÇÃO
# ============================================================
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


# ============================================================
# 1) QUERIES SQL (3)
# ============================================================

def sql_top10_livros_por_rating() -> List[Dict[str, Any]]:
    """
    Query SQL #1 — Top 10 livros pela média de rating.
    Usa dois JOINs reais e relevantes.
    """
    conn = get_sql_connection()
    cur = conn.cursor(dictionary=True)

    
    query = """
        SELECT
            b.ISBN,
            b.book_title,
            COUNT(*) AS total_ratings,
            AVG(r.book_rating) AS avg_rating
        FROM ratings r
        JOIN books b ON b.ISBN = r.ISBN
        GROUP BY b.ISBN, b.book_title
        HAVING COUNT(*) > 10
        ORDER BY avg_rating DESC
        LIMIT 10;
    """

    try:
        cur.execute(query)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def sql_top_livros_populares(limit=10) -> List[Dict[str, Any]]:
    """
    Query SQL #2 — Top livros mais populares (por nº de ratings).
    """
    conn = get_sql_connection()
    cur = conn.cursor(dictionary=True)

    query = """
        SELECT 
            b.ISBN,
            b.book_title,
            COUNT(*) AS total_ratings
        FROM ratings r
        JOIN books b ON b.ISBN = r.ISBN
        GROUP BY b.ISBN, b.book_title
        ORDER BY total_ratings DESC
        LIMIT %s;
    """

    try:
        cur.execute(query, (limit,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def sql_livros_mesmo_autor(limit=20) -> List[Dict[str, Any]]:
    """
    Query SQL #3 — Self-Join (b1, b2):
    Encontra pares de livros do mesmo autor.
    """
    conn = get_sql_connection()
    cur = conn.cursor(dictionary=True)

    query = """
        SELECT 
            b1.book_author AS author,
            b1.book_title AS book1,
            b2.book_title AS book2,
            b1.ISBN AS isbn1,
            b2.ISBN AS isbn2
        FROM books b1
        INNER JOIN books b2 
            ON b1.book_author = b2.book_author
            AND b1.ISBN < b2.ISBN
        ORDER BY author
        LIMIT %s;
    """

    try:
        cur.execute(query, (limit,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


# ============================================================
# 2) QUERIES MONGO (2)
# ============================================================

def mongo_top_users(limit=10) -> List[Dict[str, Any]]:
    """Top utilizadores Mongo pela quantidade de ratings embebidos."""
    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    pipeline = [
        {"$unwind": "$ratings"},
        {"$group": {"_id": "$ratings.user_id", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}},
        {"$limit": limit},
        {"$project": {"user_id": "$_id", "total": 1, "_id": 0}},
    ]

    try:
        return list(db.book_ratings.aggregate(pipeline))
    finally:
        client.close()


def mongo_top_localizacoes(limit=10) -> List[Dict[str, Any]]:
    """Top localizações com maior número de utilizadores."""
    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    pipeline = [
        {"$match": {"location": {"$ne": None}}},
        {"$group": {"_id": "$location", "num_users": {"$sum": 1}}},
        {"$sort": {"num_users": -1}},
        {"$limit": limit},
        {"$project": {"location": "$_id", "num_users": 1, "_id": 0}}
    ]

    try:
        return list(db.users.aggregate(pipeline))
    finally:
        client.close()


# ============================================================
# 3) QUERIES HÍBRIDAS (2)
# ============================================================

def hibrido_localizacoes_com_atividade(limit=10) -> List[Dict[str, Any]]:
    """
    Híbrido #1:
      - Top localizações Mongo
      - Para cada localização, total de ratings SQL feitos pelos users dessa zona
    """
    top_loc = mongo_top_localizacoes(limit=limit)

    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    conn = get_sql_connection()
    cur = conn.cursor(dictionary=True)

    resultados = []

    try:
        for loc in top_loc:
            local = loc["location"]

            users = list(db.users.find(
                {"location": local},
                {"_id": 0, "user_id": 1}
            ))

            user_ids = [u["user_id"] for u in users]

            if not user_ids:
                resultados.append({
                    "location": local,
                    "mongo_users": loc["num_users"],
                    "sql_total_ratings": 0
                })
                continue

            placeholders = ",".join(["%s"] * len(user_ids))

            query = f"""
                SELECT COUNT(*) AS total_ratings
                FROM ratings
                WHERE user_id IN ({placeholders})
            """

            cur.execute(query, tuple(user_ids))
            sql_data = cur.fetchone()

            resultados.append({
                "location": local,
                "mongo_users": loc["num_users"],
                "sql_total_ratings": int(sql_data["total_ratings"])
            })

        return resultados

    finally:
        cur.close()
        conn.close()
        client.close()


def hibrido_livros_populares_com_users(limit=10) -> List[Dict[str, Any]]:
    """
    Híbrido #2:
      - Top livros SQL (por nº ratings)
      - Ver quantos utilizadores Mongo avaliaram também esses livros
    """
    top_sql = sql_top_livros_populares(limit=limit)
    isbns = [b["ISBN"] for b in top_sql]

    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    pipeline = [
        {"$match": {"ISBN": {"$in": isbns}}},
        {"$unwind": "$ratings"},
        {"$group": {"_id": "$ISBN", "mongo_users": {"$addToSet": "$ratings.user_id"}}},
        {"$project": {"ISBN": "$_id", "mongo_users": 1, "_id": 0}},
    ]

    mongo_map = {d["ISBN"]: d for d in db.book_ratings.aggregate(pipeline)}

    client.close()

    final = []
    for b in top_sql:
        isbn = b["ISBN"]
        mongo = mongo_map.get(isbn, {"mongo_users": []})

        final.append({
            "ISBN": isbn,
            "book_title": b["book_title"],
            "sql_total_ratings": int(b["total_ratings"]),
            "mongo_users_count": len(mongo["mongo_users"])
        })

    return final


# ============================================================
# MAIN
# ============================================================
def main():
    pp = pprint.PrettyPrinter(indent=2)

    print("\nSQL → Top livros por média:")
    pp.pprint(sql_top10_livros_por_rating())

    print("\nSQL → Top livros mais populares:")
    pp.pprint(sql_top_livros_populares())

    print("\nSQL → Livros do mesmo autor (SELF JOIN):")
    pp.pprint(sql_livros_mesmo_autor())

    print("\nMongo → Top utilizadores (ratings embed):")
    pp.pprint(mongo_top_users())

    print("\nMongo → Top localizações:")
    pp.pprint(mongo_top_localizacoes())

    print("\nHíbrido → Localizações + atividade SQL:")
    pp.pprint(hibrido_localizacoes_com_atividade())

    print("\nHíbrido → Livros populares + users Mongo:")
    pp.pprint(hibrido_livros_populares_com_users())


if __name__ == "__main__":
    main()
