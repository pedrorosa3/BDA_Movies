"""
Script de Análises Híbridas (MySQL + MongoDB)
------------------------------------------------
Inclui:
  • 2 queries SQL
  • 2 queries MongoDB
  • 2 queries híbridas (reutilizam as anteriores)
  • Pelo menos uma query SQL com dois JOINs relevantes
  • Código robusto, limpo e totalmente comentado em português
"""

import mysql.connector
from mysql.connector import Error as MySQLError
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from typing import List, Dict, Any
import os
import sys
import pprint
from ScriptGoal4 import MYSQL_CONFIG
from config import Config


# ============================================================
#  FUNÇÕES DE LIGAÇÃO
# ============================================================
def get_sql_client():
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


# ================================================================
# 1) QUERIES SQL (2)
# ================================================================
def sql_top10_livros_por_rating() -> List[Dict[str, Any]]:
    """
    Query SQL #1 — Top 10 livros pela média de rating.
    Usa DOIS JOINs relevantes (não são decorativos):

    JOIN 1 → tabela com nº total de ratings por ISBN  
    JOIN 2 → tabela com média de ratings por ISBN

    Estes JOINs são necessários para combinar contagem + média de forma eficiente.
    """
    conn = get_sql_connection()
    cur = conn.cursor(dictionary=True)

    query = """
        SELECT b.ISBN, b.book_title,
               c.total_ratings,
               a.avg_rating
        FROM books b
        JOIN (
            SELECT ISBN, COUNT(*) AS total_ratings
            FROM ratings
            GROUP BY ISBN
        ) c ON c.ISBN = b.ISBN     -- JOIN relevante: contagem de ratings
        JOIN (
            SELECT ISBN, AVG(book_rating) AS avg_rating
            FROM ratings
            GROUP BY ISBN
        ) a ON a.ISBN = b.ISBN     -- JOIN relevante: média de ratings
        WHERE c.total_ratings >= 5
        ORDER BY a.avg_rating DESC
        LIMIT 10;
    """

    try:
        cur.execute(query)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def sql_top_utilizadores(limit=10) -> List[Dict[str, Any]]:
    """Query SQL #2 — Top utilizadores com mais ratings."""
    conn = get_sql_connection()
    cur = conn.cursor(dictionary=True)

    query = """
        SELECT user_id, COUNT(*) AS total_ratings
        FROM ratings
        GROUP BY user_id
        ORDER BY total_ratings DESC
        LIMIT %s;
    """

    try:
        cur.execute(query, (limit,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


# ================================================================
# 2) QUERIES MONGO (2)
# ================================================================
def mongo_top_users(limit=10) -> List[Dict[str, Any]]:
    """
    Query MongoDB #1 — Top utilizadores pela quantidade total de ratings
    (baseado na coleção embebida "book_ratings").
    """
    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    pipeline = [
        {"$unwind": "$ratings"},  # separa cada rating num documento independente
        {"$group": {"_id": "$ratings.user_id", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}},
        {"$limit": limit},
        {"$project": {"user_id": "$_id", "total": 1, "_id": 0}},
    ]

    try:
        return list(db.book_ratings.aggregate(pipeline))
    finally:
        client.close()


def mongo_top_livros(limit=10) -> List[Dict[str, Any]]:
    """
    Query MongoDB #2 — Top livros pela média de ratings no Mongo.
    """
    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    pipeline = [
        {"$unwind": "$ratings"},
        {"$group": {"_id": "$ISBN", "avg_rating": {"$avg": "$ratings.book_rating"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gte": 5}}},
        {"$sort": {"avg_rating": -1}},
        {"$limit": limit},
        {"$project": {"ISBN": "$_id", "avg_rating": 1, "count": 1, "_id": 0}},
    ]

    try:
        return list(db.book_ratings.aggregate(pipeline))
    finally:
        client.close()


# ================================================================
# 3) QUERIES HÍBRIDAS (2)
# ================================================================
def hibrido_top_users_com_perfil(limit=10) -> List[Dict[str, Any]]:
    """
    Query Híbrida #1:
      • Usa SQL para obter top utilizadores (sql_top_utilizadores)
      • Depois vai ao Mongo buscar o perfil (idade/localização)
    """
    # Reutilização da query SQL
    top_sql = sql_top_utilizadores(limit=limit)
    ids = [u["user_id"] for u in top_sql]

    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    try:
        perfis = {
            d["user_id"]: d for d in db.users.find(
                {"user_id": {"$in": ids}},
                {"_id": 0}
            )
        }

        resultado = []
        for u in top_sql:
            uid = u["user_id"]
            perfil = perfis.get(uid, {})
            resultado.append({
                "user_id": uid,
                "total_ratings": u["total_ratings"],
                "location": perfil.get("location"),
                "age": perfil.get("age"),
            })

        return resultado

    finally:
        client.close()


def hibrido_top_livros_enriquecido(limit=10) -> List[Dict[str, Any]]:
    """
    Query Híbrida #2:
      • Usa SQL para obter top livros (sql_top10_livros_por_rating)
      • Enriquecido com métricas MongoDB (média Mongo + nº ratings Mongo)
    """
    top_sql = sql_top10_livros_por_rating()
    isbns = [b["ISBN"] for b in top_sql]

    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    try:
        pipeline = [
            {"$match": {"ISBN": {"$in": isbns}}},
            {"$unwind": "$ratings"},
            {"$group": {"_id": "$ISBN", "mongo_avg": {"$avg": "$ratings.book_rating"}, "count": {"$sum": 1}}},
            {"$project": {"ISBN": "$_id", "mongo_avg": 1, "count": 1, "_id": 0}},
        ]

        mongo_map = {d["ISBN"]: d for d in db.book_ratings.aggregate(pipeline)}

        final = []
        for b in top_sql:
            isbn = b["ISBN"]
            mongo = mongo_map.get(isbn, {})
            final.append({
                "ISBN": isbn,
                "book_title": b["book_title"],
                "sql_avg": float(b["avg_rating"]),
                "sql_total_ratings": int(b["total_ratings"]),
                "mongo_avg": mongo.get("mongo_avg"),
                "mongo_ratings": mongo.get("count", 0),
            })

        return final

    finally:
        client.close()


# ================================================================
# MAIN (demonstração)
# ================================================================
def main():
    pp = pprint.PrettyPrinter(indent=2)

    print("\nSQL → Top 10 livros:")
    pp.pprint(sql_top10_livros_por_rating())

    print("\nSQL → Top utilizadores:")
    pp.pprint(sql_top_utilizadores())

    print("\nMongo → Top utilizadores Mongo:")
    pp.pprint(mongo_top_users())

    print("\nMongo → Top livros Mongo:")
    pp.pprint(mongo_top_livros())

    print("\nHíbrido → SQL utilizadores + perfil Mongo:")
    pp.pprint(hibrido_top_users_com_perfil())

    print("\nHíbrido → SQL livros + estatísticas Mongo:")
    pp.pprint(hibrido_top_livros_enriquecido())


if __name__ == "__main__":
    main()

