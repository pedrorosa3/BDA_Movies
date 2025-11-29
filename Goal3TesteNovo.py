#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
concurrency_demos_context.py

Demonstrações de concorrência e consistência adaptadas ao teu esquema:
- MySQL: tables -> books, ratings
- Mongo: collections -> users, book_ratings (cada doc: { ISBN, ratings: [{user_id, book_rating}, ...] })

Conteúdo:
  - 2 cenários SQL
  - 2 cenários Mongo
  - 2 cenários híbridos (reutilizam SQL/Mongo)
  - EXPLAIN / .explain() para planos
  - Medições de tempo e contagem de conflitos (retries)
  - Comentários em português (linha a linha, concisos)

Nota: ajusta Config/MYSQL/MONGO se necessário (usar module config ou variáveis de ambiente).
"""

import os
import sys
import time
import threading
import random
import pprint
from typing import Any, Dict, List, Optional
from config import Config

# try/except nas dependências para mensagens mais claras
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except Exception as e:
    print("ERRO: instale mysql-connector-python (pip install mysql-connector-python)", file=sys.stderr)
    raise

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError, OperationFailure
except Exception as e:
    print("ERRO: instale pymongo (pip install pymongo)", file=sys.stderr)
    raise


pp = pprint.PrettyPrinter(indent=2)

# --------------------------
# HELPERS DE CONEXÃO
# --------------------------
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

# --------------------------
# UTILIDADES COMUNS
# --------------------------
def safe_int(v):
    """Converte para int ou devolve None."""
    try:
        return int(v)
    except Exception:
        return None

# --------------------------
# PREPARAÇÃO (cria objetos de demo)
# --------------------------
def prepare_sql_demo_tables():
    """Cria uma tabela auxiliar 'demo_counter' e garante ratings minimal para testes."""
    conn = get_sql_connection()
    cur = conn.cursor()
    # tabela de demonstração para contadores / atomicidade
    cur.execute("""
        CREATE TABLE IF NOT EXISTS demo_counter (
            id INT PRIMARY KEY,
            cnt INT
        ) ENGINE=InnoDB;
    """)
    # garantir linha
    cur.execute("INSERT IGNORE INTO demo_counter (id, cnt) VALUES (1, 0);")
    # criar tabelas simplificadas se não existirem (books, ratings) — estrutura mínima
    cur.execute("""
        CREATE TABLE IF NOT EXISTS books (
            ISBN VARCHAR(20) PRIMARY KEY,
            book_title TEXT
        ) ENGINE=InnoDB;
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            user_id INT,
            ISBN VARCHAR(20),
            book_rating INT,
            PRIMARY KEY (user_id, ISBN),
            FOREIGN KEY (ISBN) REFERENCES books(ISBN)
              ON UPDATE CASCADE ON DELETE CASCADE
        ) ENGINE=InnoDB;
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("[SQL] Tabelas de demo preparadas (demo_counter, books, ratings).")

def prepare_mongo_demo_collections():
    """Cria documentos demo em Mongo: demo_counters, book_ratings e users."""
    client = get_mongo_client()
    db = client[Config.MONGO_DB]
    # contador
    db.demo_counters.update_one({"_id": "counter1"}, {"$set": {"cnt": 0}}, upsert=True)
    # exemplo book_ratings (um doc por ISBN com array ratings)
    db.book_ratings.update_one({"ISBN": "ISBN-DEMO"}, {"$set": {"ratings": []}}, upsert=True)
    # users collection minimal
    db.users.update_one({"user_id": 1}, {"$set": {"user_id": 1, "location": "PT", "age": 30}}, upsert=True)
    client.close()
    print("[Mongo] Collections demo preparadas (demo_counters, book_ratings, users).")

# --------------------------
# EXPLAIN helpers
# --------------------------
def explain_mysql(query: str, params: Optional[tuple] = None):
    """Imprime EXPLAIN para uma query SQL (útil para planos e índices)."""
    conn = get_sql_connection()
    cur = conn.cursor()
    try:
        cur.execute("EXPLAIN " + query, params or ())
        rows = cur.fetchall()
        print("[MySQL] EXPLAIN para:", query)
        for r in rows:
            print("  ", r)
    finally:
        cur.close()
        conn.close()

def explain_mongo(collection: str, filter_doc: dict):
    """Imprime explain() para um find em Mongo (sumário do queryPlanner)."""
    client = get_mongo_client()
    db = client[Config.MONGO_DB]
    coll = db[collection]
    try:
        plan = coll.find(filter_doc).explain()
        print("[Mongo] explain() summary para", collection, "filter:", filter_doc)
        print(plan.get("queryPlanner", {}))
    finally:
        client.close()

# --------------------------
# SQL SCENARIOS
# --------------------------
def sql_lost_update_demo(iterations: int = 3, increment: int = 1):
    """Demonstra lost update em MySQL: read-modify-write sem transacção -> perda."""
    print("\n[SQL] LOST UPDATE demo (sem transacções)")
    # reset
    conn = get_sql_connection(); cur = conn.cursor()
    cur.execute("UPDATE demo_counter SET cnt = 0 WHERE id = 1"); conn.commit(); cur.close(); conn.close()

    conflicts = 0
    def worker(name):
        nonlocal conflicts
        try:
            conn = get_sql_connection(); cur = conn.cursor()
            cur.execute("SELECT cnt FROM demo_counter WHERE id = 1")
            val = cur.fetchone()[0]
            print(f"[{name}] leu {val}")
            # simular trabalho
            time.sleep(0.15)
            new = val + increment
            # escreve sem transacção sincronizada
            cur.execute("UPDATE demo_counter SET cnt = %s WHERE id = 1", (new,))
            conn.commit()
            print(f"[{name}] escreveu {new}")
        except Exception as e:
            print(f"[{name}] ERRO:", e); conflicts += 1
        finally:
            try: cur.close(); conn.close()
            except: pass

    threads = []
    for i in range(iterations):
        t = threading.Thread(target=worker, args=(f"T{i+1}",))
        threads.append(t); t.start()
    for t in threads: t.join()

    conn = get_sql_connection(); cur = conn.cursor()
    cur.execute("SELECT cnt FROM demo_counter WHERE id = 1"); final = cur.fetchone()[0]; cur.close(); conn.close()
    print("[SQL] Resultado final (deveria ser", iterations*increment, "):", final, "conflicts:", conflicts)

def sql_lost_update_fix_for_update(iterations: int = 3, increment: int = 1):
    """Resolve lost update usando SELECT ... FOR UPDATE dentro de transacção."""
    print("\n[SQL] Solução LOST UPDATE com SELECT ... FOR UPDATE (transacção)")
    # reset
    conn = get_sql_connection(); cur = conn.cursor()
    cur.execute("UPDATE demo_counter SET cnt = 0 WHERE id = 1"); conn.commit(); cur.close(); conn.close()

    def worker(name):
        try:
            conn = get_sql_connection()
            # iniciar transacção explicitamente
            conn.start_transaction(isolation_level='REPEATABLE READ')
            cur = conn.cursor()
            cur.execute("SELECT cnt FROM demo_counter WHERE id = 1 FOR UPDATE")
            val = cur.fetchone()[0]
            print(f"[{name}] (locked) leu {val}")
            time.sleep(0.15)
            new = val + increment
            cur.execute("UPDATE demo_counter SET cnt = %s WHERE id = 1", (new,))
            conn.commit()
            print(f"[{name}] (locked) escreveu {new} e fez commit")
        except Exception as e:
            print(f"[{name}] ERRO:", e)
            try: conn.rollback()
            except: pass
        finally:
            try: cur.close(); conn.close()
            except: pass

    threads = []
    for i in range(iterations):
        t = threading.Thread(target=worker, args=(f"T{i+1}",))
        threads.append(t); t.start()
    for t in threads: t.join()

    conn = get_sql_connection(); cur = conn.cursor()
    cur.execute("SELECT cnt FROM demo_counter WHERE id = 1"); final = cur.fetchone()[0]; cur.close(); conn.close()
    print("[SQL] Resultado final (esperado", iterations*increment, "):", final)

# --------------------------
# SQL EXPLAIN / exemplo com JOINs relevantes
# --------------------------
def sql_explain_example_top_books():
    """Mostra EXPLAIN para uma query com JOINs relevantes entre books e ratings."""
    query = """
        SELECT b.ISBN, b.book_title, AVG(r.book_rating) AS avg_rating, COUNT(*) AS cnt
        FROM books b
        JOIN ratings r ON r.ISBN = b.ISBN
        GROUP BY b.ISBN, b.book_title
        HAVING cnt >= 5
        ORDER BY avg_rating DESC
        LIMIT 10
    """
    explain_mysql(query)

# --------------------------
# MONGO SCENARIOS
# --------------------------
def mongo_lost_update_demo(iterations: int = 3, increment: int = 1):
    """Demonstra lost update em Mongo: read-modify-write sem atomicidade (por documento pode ainda haver perda)."""
    print("\n[Mongo] LOST UPDATE demo (read-modify-write)")

    client = get_mongo_client(); db = client[Config.MONGO_DB]; coll = db.demo_counters
    coll.update_one({"_id": "counter1"}, {"$set": {"cnt": 0}})
    def worker(name):
        try:
            doc = coll.find_one({"_id": "counter1"})
            val = doc.get("cnt", 0)
            print(f"[{name}] leu {val}")
            time.sleep(0.15)
            new = val + increment
            coll.update_one({"_id": "counter1"}, {"$set": {"cnt": new}})
            print(f"[{name}] escreveu {new}")
        except Exception as e:
            print(f"[{name}] ERRO:", e)
    threads = []
    for i in range(iterations):
        t = threading.Thread(target=worker, args=(f"T{i+1}",)); threads.append(t); t.start()
    for t in threads: t.join()
    final = coll.find_one({"_id": "counter1"}).get("cnt"); client.close()
    print("[Mongo] Resultado final (deveria ser", iterations*increment, "):", final)

def mongo_atomic_solution_inc(iterations: int = 3, increment: int = 1):
    """Solução Mongo: usar operador atómico $inc (operações atómicas por documento)."""
    print("\n[Mongo] Solução: operador $inc atómico")
    client = get_mongo_client(); db = client[Config.MONGO_DB]; coll = db.demo_counters
    coll.update_one({"_id": "counter1"}, {"$set": {"cnt": 0}})
    def worker(name):
        try:
            coll.update_one({"_id": "counter1"}, {"$inc": {"cnt": increment}})
            print(f"[{name}] fez $inc +{increment}")
        except Exception as e:
            print(f"[{name}] ERRO:", e)
    threads = []
    for i in range(iterations):
        t = threading.Thread(target=worker, args=(f"T{i+1}",)); threads.append(t); t.start()
    for t in threads: t.join()
    final = coll.find_one({"_id": "counter1"}).get("cnt"); client.close()
    print("[Mongo] Resultado final (esperado", iterations*increment, "):", final)

def mongo_transaction_demo():
    """Demonstra transacção multi-documento em Mongo (se suportado pelo servidor)."""
    print("\n[Mongo] Demo de transacção multi-documento (requer replica set)")
    client = get_mongo_client(); db = client[Config.MONGO_DB]
    coll = db.demo_counters; other = db.demo_other
    # preparar
    coll.update_one({"_id": "counter1"}, {"$set": {"cnt": 0}}, upsert=True)
    other.update_one({"_id": "x"}, {"$set": {"val": 0}}, upsert=True)
    try:
        with client.start_session() as session:
            with session.start_transaction():
                coll.update_one({"_id": "counter1"}, {"$inc": {"cnt": 5}}, session=session)
                other.update_one({"_id": "x"}, {"$inc": {"val": 1}}, session=session)
                print("[Mongo] dentro da transacção: updates feitos; a seguir vamos abortar para demonstrar rollback")
                raise RuntimeError("Simular rollback")
    except RuntimeError as e:
        print("[Mongo] Simulação de rollback:", e)
    except Exception as e:
        print("[Mongo] Não foi possível executar transacção (provavelmente sem suporte):", e)
    finally:
        client.close()

# --------------------------
# HYBRID SCENARIOS
# --------------------------
def hybrid_sql_to_mongo_enrich_top_users(limit: int = 5):
    """
    Hybrid #1: obter top users por número de ratings em SQL e enriquecer com perfil em Mongo.
    Mostra possibilidade de inconsistência se houver concorrência (ex.: ratings inseridos entre SQL read e Mongo read).
    """
    print("\n[Hybrid] SQL -> Mongo: top users by ratings count enriched with Mongo profile")
    # 1) SQL: top users by count
    conn = get_sql_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT user_id, COUNT(*) AS ratings_count
        FROM ratings
        GROUP BY user_id
        ORDER BY ratings_count DESC
        LIMIT %s
    """, (limit,))
    top = cur.fetchall()
    cur.close(); conn.close()
    pp.pprint(top)
    # 2) Mongo: fetch profiles for these user_ids
    user_ids = [r["user_id"] for r in top if r.get("user_id") is not None]
    client = get_mongo_client(); db = client[Config.MONGO_DB]
    profiles = {u["user_id"]: u for u in db.users.find({"user_id": {"$in": user_ids}}, {"_id": 0})}
    # 3) Merge and mostrar (note que ratings_count vem do snapshot SQL)
    merged = []
    for r in top:
        uid = r["user_id"]
        merged.append({
            "user_id": uid,
            "ratings_count": r["ratings_count"],
            "profile": profiles.get(uid)
        })
    client.close()
    pp.pprint(merged)
    print("[Hybrid] Nota: se novos ratings forem inseridos entre o SELECT SQL e a leitura Mongo, os counts não reflectem o estado actual -> inconsistencia eventual.")

def hybrid_mongo_to_sql_book_stats(isbn: str = "ISBN-DEMO"):
    """
    Hybrid #2: obter estatísticas agregadas de ratings em Mongo e armazenar / comparar com agregação SQL.
    Demostra divergências se houver concorrência e não se usarem locks/transacções.
    """
    print("\n[Hybrid] Mongo -> SQL: aggregate ratings from Mongo and compare/store in SQL table")
    client = get_mongo_client(); db = client[Config.MONGO_DB]
    # agregação Mongo
    pipeline = [
        {"$match": {"ISBN": isbn}},
        {"$unwind": "$ratings"},
        {"$group": {"_id": "$ISBN", "avg_rating": {"$avg": "$ratings.book_rating"}, "count": {"$sum": 1}}},
        {"$project": {"ISBN": "$_id", "avg_rating": 1, "count": 1, "_id": 0}}
    ]
    mongo_stats = list(db.book_ratings.aggregate(pipeline))
    print("[Hybrid] stats from Mongo aggregation:")
    pp.pprint(mongo_stats)
    # SQL aggregation (snapshot)
    conn = get_sql_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT AVG(book_rating) AS avg_rating, COUNT(*) AS count
        FROM ratings
        WHERE ISBN = %s
    """, (isbn,))
    sql_stats = cur.fetchone()
    cur.close(); conn.close()
    print("[Hybrid] stats from SQL aggregation:")
    pp.pprint(sql_stats)
    # fechar
    client.close()
    print("[Hybrid] Nota: se ratings foram inseridos simultaneamente em SQL e Mongo, as duas agregações podem divergir -> precisa de estratégia de sincronização / atomicidade para manter consistência.")

# --------------------------
# FUNÇÃO PRINCIPAL DEMO
# --------------------------
def run_all_demos():
    print("=== Preparando ambiente de demonstração (contexto: books/ratings/users) ===")
    prepare_sql_demo_tables()
    prepare_mongo_demo_collections()
    time.sleep(0.5)

    print("\n=== EXPLAINs e planos ===")
    sql_explain_example_top_books()
    explain_mongo("book_ratings", {"ISBN": "ISBN-DEMO"})

    print("\n=== Cenários MySQL ===")
    sql_lost_update_demo(iterations=3, increment=1)
    sql_lost_update_fix_for_update(iterations=3, increment=1)

    print("\n=== Cenários Mongo ===")
    mongo_lost_update_demo(iterations=3, increment=1)
    mongo_atomic_solution_inc(iterations=3, increment=1)
    mongo_transaction_demo()

    print("\n=== Cenários híbridos ===")
    hybrid_sql_to_mongo_enrich_top_users(limit=5)
    hybrid_mongo_to_sql_book_stats(isbn="ISBN-DEMO")

    print("\n=== Demo concluída ===")

# --------------------------
# ENTRYPOINT
# --------------------------
if __name__ == "__main__":
    run_all_demos()
