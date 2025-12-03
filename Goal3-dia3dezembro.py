#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
concurrency_demos_project.py

Demonstrações de concorrência e consistência aplicadas ao contexto do projeto
(tabelas: books, ratings, users). O script mostra cenários clássicos (lost update,
dirty read, non-repeatable read, phantom, serializable) em MySQL e equivalentes em MongoDB,
usa EXPLAIN / .explain() para planos, mede tempos e conta conflitos.

Como usar:
- Ajusta as variáveis de ligação no módulo `Config` (ou em variáveis de ambiente).
- Executa: python concurrency_demos_project.py
- Mostra resultados no stdout; cada função é autónoma e documentada.

Nota: algumas funcionalidades Mongo (transacções multi-doc) requerem replica-set.
"""

from typing import Optional, Dict, Any, List
import threading
import time
import sys
import pprint

# Tenta importar dependências; mensagem clara se faltar algo
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except Exception as e:
    print("ERRO: mysql-connector-python não encontrado. Instala com: pip install mysql-connector-python")
    raise

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError, OperationFailure
except Exception as e:
    print("ERRO: pymongo não encontrado. Instala com: pip install pymongo")
    raise

# Importa Config do teu projeto; espera que contenha MYSQL_* e MONGO settings
try:
    from config import Config  # deve expor MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB, build_mongo_uri(), MONGO_DB
except Exception:
    # Fallback com informações de exemplo — ajusta conforme necessário
    class Config:
        MYSQL_HOST = "localhost"
        MYSQL_USER = "root"
        MYSQL_PASSWORD = "<password>"
        MYSQL_DB = "bda_Group11"
        MYSQL_PORT = 3306
        MONGO_HOST = "localhost"
        MONGO_PORT = 27017
        MONGO_DB = "bda_Group11"

        @staticmethod
        def build_mongo_uri():
            return f"mongodb://root:<password>@{Config.MONGO_HOST}:{Config.MONGO_PORT}/"


pp = pprint.PrettyPrinter(indent=2)

# -----------------------
# Helpers de conexão
# -----------------------
def get_sql_connection():
    """Cria e devolve conexão MySQL (levanta em caso de erro)."""
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            port=getattr(Config, "MYSQL_PORT", 3306),
            autocommit=False  # controlamos commits manualmente
        )
        return conn
    except MySQLError as e:
        print("Falha ao ligar ao MySQL:", e, file=sys.stderr)
        raise

def get_mongo_client():
    """Cria e devolve Mongo client (levanta em caso de erro)."""
    try:
        client = MongoClient(Config.build_mongo_uri())
        return client
    except PyMongoError as e:
        print("Falha ao ligar ao MongoDB:", e, file=sys.stderr)
        raise

# -----------------------
# Preparação do ambiente (tabelas/collections de demonstração)
# -----------------------
def prepare_demo_sql_tables():
    """
    Prepara tabelas de demonstração relacionadas ao projeto: demo_counters (para testes),
    e garante que existem books e ratings com alguns dados mínimos (não remove dados existentes).
    """
    conn = get_sql_connection()
    cur = conn.cursor()
    try:
        # tabela auxiliar para demonstrações (contador)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS demo_counter (
                id INT PRIMARY KEY,
                cnt INT
            ) ENGINE=InnoDB;
        """)
        # assegura linha id=1
        cur.execute("INSERT INTO demo_counter (id, cnt) VALUES (1, 0) ON DUPLICATE KEY UPDATE cnt = cnt;")

        # Garantir índices úteis nas tabelas do projeto, sem destruir dados
        cur.execute("""
            CREATE TABLE IF NOT EXISTS books (
                ISBN VARCHAR(20) PRIMARY KEY,
                book_title TEXT
            ) ENGINE=InnoDB;
        """)  # se já existir, isto não altera

        cur.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                user_id INT,
                ISBN VARCHAR(20),
                book_rating INT,
                PRIMARY KEY (user_id, ISBN)
            ) ENGINE=InnoDB;
        """)  # se já existir, isto não altera

        # índices que ajudam nos SELECTs
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ratings_isbn ON ratings (ISBN);")
        except Exception:
            # MySQL < 8 não tem CREATE INDEX IF NOT EXISTS — ignorar error não fatal
            try:
                cur.execute("CREATE INDEX idx_ratings_isbn ON ratings (ISBN);")
            except Exception:
                pass

        conn.commit()
        print("[SQL] Tabelas de demo preparadas (demo_counter, books, ratings).")
    finally:
        cur.close()
        conn.close()

def prepare_demo_mongo_collections():
    """
    Prepara collections de demonstração no Mongo:
    - demo_counters: documento _id='counter1' para testes de concorrência
    - book_ratings, users: colecções usadas pelo projeto
    """
    client = get_mongo_client()
    db = client[Config.MONGO_DB]
    try:
        db.demo_counters.update_one({"_id": "counter1"}, {"$set": {"cnt": 0}}, upsert=True)
        # não sobrescreve book_ratings/users caso já existam — apenas garante existência
        print("[Mongo] Collections demo preparadas (demo_counters, book_ratings, users).")
    finally:
        client.close()

# -----------------------
# Utilitários explain / medidas
# -----------------------
def explain_mysql(query: str, params: Optional[tuple] = None):
    """Executa EXPLAIN para uma query e imprime o resultado (útil para análise)."""
    conn = get_sql_connection()
    cur = conn.cursor()
    try:
        cur.execute("EXPLAIN " + query, params or ())
        rows = cur.fetchall()
        print("[MySQL] EXPLAIN para:")
        print(query)
        for r in rows:
            print("  ", r)
    finally:
        cur.close()
        conn.close()

def explain_mongo(collection_name: str, filter_doc: dict):
    """Executa .explain() num find() e imprime o sumário do plano."""
    client = get_mongo_client()
    db = client[Config.MONGO_DB]
    coll = db[collection_name]
    try:
        plan = coll.find(filter_doc).explain()
        print("[Mongo] explain() summary para", collection_name, "filter:", filter_doc)
        print(plan.get("queryPlanner", {}))
    finally:
        client.close()

# -----------------------
# MySQL Scenarios (project-adapted)
# -----------------------
def mysql_concurrent_reads_test(concurrent_clients: int = 10, rounds: int = 50):
    """
    Test 1 - Concurrent reads: vários clients a executar SELECTs sobre ratings/books.
    Mede throughput e latências médias.
    """
    print("\n[SQL] Test 1 - Concurrent Reads (SELECT heavy)")
    conn = get_sql_connection()
    cur = conn.cursor()
    try:
        # Query representativa do projecto: top books (light)
        query = """
            SELECT b.book_title, COUNT(*) AS total_ratings
            FROM ratings r JOIN books b ON b.ISBN = r.ISBN
            GROUP BY r.ISBN
            ORDER BY total_ratings DESC
            LIMIT 10;
        """
        # spawn threads que executam a query várias vezes
        latencies = []
        def worker():
            nonlocal latencies
            c = get_sql_connection()
            curw = c.cursor()
            for _ in range(rounds):
                t0 = time.time()
                curw.execute(query)
                _ = curw.fetchall()
                t1 = time.time()
                latencies.append(t1 - t0)
            curw.close()
            c.close()
        threads = [threading.Thread(target=worker) for _ in range(concurrent_clients)]
        start = time.time()
        for t in threads: t.start()
        for t in threads: t.join()
        total_time = time.time() - start
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        print(f"[SQL] Concurrent reads: clients={concurrent_clients}, total_requests={len(latencies)}, total_time={total_time:.3f}s, avg_latency={avg_latency:.4f}s")
    finally:
        cur.close()
        conn.close()

def mysql_lost_update_unsafe(iterations: int = 3):
    """
    Test 2 - Lost update: dois/mais threads leem, modificam e escrevem sem transacção coerente.
    Usa demo_counter.id=1 (simples) para demonstrar.
    """
    print("\n[SQL] Test 2 - Lost update (unsafe read-modify-write)")

    def worker(name):
        c = get_sql_connection()
        curw = c.cursor()
        try:
            curw.execute("SELECT cnt FROM demo_counter WHERE id = 1;")
            cur_val = curw.fetchone()[0]
            print(f"[{name}] leu {cur_val}")
            time.sleep(0.2)
            new = cur_val + 1
            curw.execute("UPDATE demo_counter SET cnt = %s WHERE id = 1;", (new,))
            c.commit()
            print(f"[{name}] escreveu {new}")
        except Exception as e:
            print(f"[{name}] ERRO:", e)
        finally:
            curw.close()
            c.close()

    # reset
    c0 = get_sql_connection()
    cur0 = c0.cursor()
    cur0.execute("UPDATE demo_counter SET cnt = 0 WHERE id = 1;")
    c0.commit()
    cur0.close()
    c0.close()

    threads = [threading.Thread(target=worker, args=(f"T{i+1}",)) for i in range(iterations)]
    for t in threads: t.start()
    for t in threads: t.join()

    # resultado
    c1 = get_sql_connection()
    cur1 = c1.cursor()
    cur1.execute("SELECT cnt FROM demo_counter WHERE id = 1;")
    final = cur1.fetchone()[0]
    cur1.close()
    c1.close()
    print("[SQL] Resultado final (deveria ser", iterations, "):", final)

def mysql_lost_update_with_for_update(iterations: int = 3):
    """
    Test 3 - Solução: SELECT ... FOR UPDATE dentro de transacção (pessimistic locking).
    Garante serialização dos updates.
    """
    print("\n[SQL] Test 3 - Lost update resolvido com SELECT ... FOR UPDATE (transacção)")

    def worker(name):
        c = get_sql_connection()
        try:
            # iniciar transacção manualmente
            c.start_transaction(isolation_level='REPEATABLE READ')
            curw = c.cursor()
            curw.execute("SELECT cnt FROM demo_counter WHERE id = 1 FOR UPDATE;")
            cur_val = curw.fetchone()[0]
            print(f"[{name}] (lock) leu {cur_val}")
            time.sleep(0.15)
            new = cur_val + 1
            curw.execute("UPDATE demo_counter SET cnt = %s WHERE id = 1;", (new,))
            c.commit()
            print(f"[{name}] (lock) escreveu {new} e fez commit")
        except Exception as e:
            print(f"[{name}] ERRO:", e)
            try:
                c.rollback()
            except:
                pass
        finally:
            try:
                curw.close()
            except:
                pass
            c.close()

    # reset
    c0 = get_sql_connection()
    cur0 = c0.cursor()
    cur0.execute("UPDATE demo_counter SET cnt = 0 WHERE id = 1;")
    c0.commit()
    cur0.close()
    c0.close()

    threads = [threading.Thread(target=worker, args=(f"T{i+1}",)) for i in range(iterations)]
    for t in threads: t.start()
    for t in threads: t.join()

    c1 = get_sql_connection()
    cur1 = c1.cursor()
    cur1.execute("SELECT cnt FROM demo_counter WHERE id = 1;")
    final = cur1.fetchone()[0]
    cur1.close()
    c1.close()
    print("[SQL] Resultado final (esperado", iterations, "):", final)

def mysql_dirty_read_demo():
    """
    Test 4 - Dirty read demo: demonstra leitura suja quando uma sessão escreve e não comita
    e outra sessão está em READ UNCOMMITTED.
    """
    print("\n[SQL] Test 4 - Dirty read demo (READ UNCOMMITTED)")

    # reset
    c0 = get_sql_connection()
    cur0 = c0.cursor()
    cur0.execute("UPDATE demo_counter SET cnt = 0 WHERE id = 1;")
    c0.commit()
    cur0.close()
    c0.close()

    def thread_a():
        c = get_sql_connection()
        cur = c.cursor()
        c.start_transaction()
        cur.execute("SELECT cnt FROM demo_counter WHERE id = 1;")
        v = cur.fetchone()[0]
        print("[A] leu (antes):", v)
        cur.execute("UPDATE demo_counter SET cnt = %s WHERE id = 1;", (999,))
        print("[A] escreveu 999 (sem commit) e espera")
        time.sleep(2)
        print("[A] faz ROLLBACK")
        c.rollback()
        cur.close()
        c.close()

    def thread_b():
        time.sleep(0.5)
        c = get_sql_connection()
        cur = c.cursor()
        # mudar isolamento da sessão para permitir dirty reads
        cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;")
        c.commit()
        cur.execute("SELECT cnt FROM demo_counter WHERE id = 1;")
        v = cur.fetchone()[0]
        print("[B] leu em READ UNCOMMITTED:", v)
        cur.close()
        c.close()

    ta = threading.Thread(target=thread_a)
    tb = threading.Thread(target=thread_b)
    ta.start(); tb.start()
    ta.join(); tb.join()

    c = get_sql_connection(); cur = c.cursor()
    cur.execute("SELECT cnt FROM demo_counter WHERE id = 1;")
    final = cur.fetchone()[0]
    cur.close(); c.close()
    print("[SQL] Valor final após rollback (esperado 0):", final)

def mysql_non_repeatable_read_demo():
    """
    Test 5 - Non-repeatable read:
    - Transacção A lê valor, espera; Transacção B altera e comita; A lê novamente.
    - Em READ COMMITTED A verá a alteração (não-repeatable); em REPEATABLE READ A não vê.
    """
    print("\n[SQL] Test 5 - Non-repeatable read demo")

    # reset
    c0 = get_sql_connection(); cur0 = c0.cursor()
    cur0.execute("UPDATE demo_counter SET cnt = 0 WHERE id = 1;")
    c0.commit(); cur0.close(); c0.close()

    def tx_reader(isolation_level='READ COMMITTED'):
        c = get_sql_connection()
        # definir isolation level da sessão
        c.start_transaction(isolation_level=isolation_level)
        cur = c.cursor()
        cur.execute("SELECT cnt FROM demo_counter WHERE id = 1;")
        v1 = cur.fetchone()[0]
        print(f"[Reader-{isolation_level}] primeira leitura:", v1)
        time.sleep(1)  # esperar que writer altere
        cur.execute("SELECT cnt FROM demo_counter WHERE id = 1;")
        v2 = cur.fetchone()[0]
        print(f"[Reader-{isolation_level}] segunda leitura:", v2)
        try:
            c.commit()
        except:
            pass
        cur.close(); c.close()

    def tx_writer():
        time.sleep(0.3)
        c = get_sql_connection(); cur = c.cursor()
        cur.execute("UPDATE demo_counter SET cnt = 5 WHERE id = 1;")
        c.commit()
        cur.close(); c.close()
        print("[Writer] fez UPDATE cnt = 5 e comitou")

    # correr duas sessões para comparar
    tr = threading.Thread(target=tx_reader, args=('READ COMMITTED',))
    tw = threading.Thread(target=tx_writer)
    tr.start(); tw.start(); tr.join(); tw.join()

def mysql_phantom_read_demo():
    """
    Test 6 - Phantom read:
    - Transacção A conta linhas com certa condição; Transacção B insere linha que satisfaz; A lê novamente.
    - Em REPEATABLE READ/Serializable behaviour podemos observar diferenças.
    """
    print("\n[SQL] Test 6 - Phantom read demo")

    conn = get_sql_connection(); cur = conn.cursor()
    # criar tabela de phantom demos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS demo_phantoms (
            id INT AUTO_INCREMENT PRIMARY KEY,
            val INT
        ) ENGINE=InnoDB;
    """)
    conn.commit()

    # limpar e inserir 1 linha (val = 1)
    cur.execute("DELETE FROM demo_phantoms;")
    cur.execute("INSERT INTO demo_phantoms (val) VALUES (1);")
    conn.commit()

    def reader():
        c = get_sql_connection()
        c.start_transaction(isolation_level='REPEATABLE READ')
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM demo_phantoms WHERE val >= 1;")
        cnt1 = cur.fetchone()[0]
        print("[Reader] primeira contagem:", cnt1)
        time.sleep(0.6)
        cur.execute("SELECT COUNT(*) FROM demo_phantoms WHERE val >= 1;")
        cnt2 = cur.fetchone()[0]
        print("[Reader] segunda contagem:", cnt2)
        cur.close(); c.close()

    def inserter():
        time.sleep(0.2)
        c = get_sql_connection(); cur = c.cursor()
        cur.execute("INSERT INTO demo_phantoms (val) VALUES (2);")
        c.commit()
        cur.close(); c.close()
        print("[Inserter] inseriu nova linha que pode causar phantom")

    tr = threading.Thread(target=reader); ti = threading.Thread(target=inserter)
    tr.start(); ti.start(); tr.join(); ti.join()

def mysql_serializable_demo():
    """
    Test 7 - SERIALIZABLE isolation: demonstra que inserts concorrentes podem ser bloqueados
    (dependente de engine/versão).
    """
    print("\n[SQL] Test 7 - SERIALIZABLE demo")
    conn = get_sql_connection(); cur = conn.cursor()
    # criar tabela para teste
    cur.execute("""
        CREATE TABLE IF NOT EXISTS demo_serializable (
            id INT PRIMARY KEY,
            val INT
        ) ENGINE=InnoDB;
    """)
    conn.commit()
    # limpar e inserir
    try:
        cur.execute("DELETE FROM demo_serializable;")
        cur.execute("INSERT INTO demo_serializable (id, val) VALUES (1, 100) ON DUPLICATE KEY UPDATE val = val;")
        conn.commit()
    except Exception:
        conn.rollback()
    cur.close(); conn.close()

    def tx_insert(name, new_id):
        c = get_sql_connection()
        try:
            c.start_transaction(isolation_level='SERIALIZABLE')
            curw = c.cursor()
            # tentativa de inserir uma linha com id diferente
            curw.execute("INSERT INTO demo_serializable (id, val) VALUES (%s, %s);", (new_id, 1))
            c.commit()
            print(f"[{name}] inseriu id={new_id}")
        except Exception as e:
            print(f"[{name}] ERRO (provavelmente bloqueio/conflict):", e)
            try:
                c.rollback()
            except:
                pass
        finally:
            try:
                curw.close()
            except:
                pass
            c.close()

    # duas threads tentam inserir ids diferentes mas no modo serializable podem ocorrer erros / bloqueios
    t1 = threading.Thread(target=tx_insert, args=("T1", 2))
    t2 = threading.Thread(target=tx_insert, args=("T2", 3))
    t1.start(); t2.start(); t1.join(); t2.join()

# -----------------------
# Mongo Scenarios (project-adapted)
# -----------------------
def mongo_lost_update_read_modify_write(iterations: int = 3):
    """
    Demonstra lost-update no contexto Mongo: ler-modificar-escrever sem operador atómico.
    Document demo: demo_counters._id='counter1'
    """
    print("\n[Mongo] Test - lost update (read-modify-write)")

    client = get_mongo_client()
    db = client[Config.MONGO_DB]
    coll = db.demo_counters

    coll.update_one({"_id": "counter1"}, {"$set": {"cnt": 0}}, upsert=True)

    def worker(name):
        doc = coll.find_one({"_id": "counter1"})
        cur = doc.get("cnt", 0)
        print(f"[{name}] leu {cur}")
        time.sleep(0.15)
        coll.update_one({"_id": "counter1"}, {"$set": {"cnt": cur + 1}})
        print(f"[{name}] escreveu {cur+1}")

    threads = [threading.Thread(target=worker, args=(f"T{i+1}",)) for i in range(iterations)]
    for t in threads: t.start()
    for t in threads: t.join()

    final = coll.find_one({"_id": "counter1"}).get("cnt")
    client.close()
    print("[Mongo] Resultado final (deveria ser", iterations, "):", final)

def mongo_atomic_inc_solution(iterations: int = 3):
    """
    Solução Mongo: usar $inc atómico, que evita lost-update na maioria dos cenários por documento.
    """
    print("\n[Mongo] Test - solução com $inc atómico")

    client = get_mongo_client()
    db = client[Config.MONGO_DB]
    coll = db.demo_counters

    coll.update_one({"_id": "counter1"}, {"$set": {"cnt": 0}}, upsert=True)

    def worker(name):
        coll.update_one({"_id": "counter1"}, {"$inc": {"cnt": 1}})
        print(f"[{name}] fez $inc")
    threads = [threading.Thread(target=worker, args=(f"T{i+1}",)) for i in range(iterations)]
    for t in threads: t.start()
    for t in threads: t.join()

    final = coll.find_one({"_id": "counter1"}).get("cnt")
    client.close()
    print("[Mongo] Resultado final (esperado", iterations, "):", final)

def mongo_transaction_demo():
    """
    Demonstração de transacção multi-documento (apenas funciona em replica-set).
    Tenta fazer commit e forçar rollback para demonstrar atomicidade.
    """
    print("\n[Mongo] Test - transacção multi-documento (se suportado)")
    client = get_mongo_client()
    db = client[Config.MONGO_DB]
    coll = db.demo_counters
    other = db.demo_other

    coll.update_one({"_id": "counter1"}, {"$set": {"cnt": 0}}, upsert=True)
    other.update_one({"_id": "x"}, {"$set": {"val": 0}}, upsert=True)

    try:
        with client.start_session() as session:
            with session.start_transaction():
                coll.update_one({"_id": "counter1"}, {"$inc": {"cnt": 5}}, session=session)
                other.update_one({"_id": "x"}, {"$inc": {"val": 1}}, session=session)
                # forçar rollback simulando erro
                raise RuntimeError("Simular rollback")
    except RuntimeError as e:
        print("[Mongo] Simulação de rollback; transacção abortada:", e)
    except Exception as e:
        print("[Mongo] Não foi possível executar transacção (provavelmente sem suporte):", e)
    finally:
        client.close()

# -----------------------
# Hybrid examples (SQL+Mongo)
# -----------------------
def hybrid_sql_top_users_enrich_with_mongo(limit: int = 5):
    """
    Hybrid #1:
    - SQL: obter top users por número de ratings (rápido em SQL).
    - Mongo: enriquecer perfil de cada user (location, age) via lookup em users collection.
    Demonstra discrepância potencial se inserts ocorrerem entre operações.
    """
    print("\n[Hybrid] SQL -> Mongo: top users enriched with mongo profile")
    conn = get_sql_connection(); cur = conn.cursor(dictionary=True)
    query = "SELECT user_id, COUNT(*) AS cnt FROM ratings GROUP BY user_id ORDER BY cnt DESC LIMIT %s;"
    cur.execute(query, (limit,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    user_ids = [r["user_id"] for r in rows]
    client = get_mongo_client(); db = client[Config.MONGO_DB]
    mongo_users = {u["user_id"]: u for u in db.users.find({"user_id": {"$in": user_ids}}, {"_id": 0})}
    merged = []
    for r in rows:
        uid = r["user_id"]
        merged.append({
            "user_id": uid,
            "ratings_count": r["cnt"],
            "profile": mongo_users.get(uid)
        })
    client.close()
    pp.pprint(merged)
    print("[Hybrid] Nota: se novos ratings forem inseridos entre o SELECT SQL e a leitura Mongo, resultados podem divergir (consistência eventual).")

def hybrid_mongo_aggregate_compare_to_sql():
    """
    Hybrid #2:
    - Mongo: agrega ratings por ISBN (avg/count) a partir de book_ratings (embedded).
    - SQL: agrega ratings por ISBN a partir de tabela ratings.
    - Compara os dois resultados e mostra divergências.
    """
    print("\n[Hybrid] Mongo aggregation -> comparar com SQL aggregation")
    client = get_mongo_client(); db = client[Config.MONGO_DB]
    pipeline = [
        {"$unwind": "$ratings"},
        {"$group": {"_id": "$ISBN", "avg": {"$avg": "$ratings.book_rating"}, "cnt": {"$sum": 1}}},
        {"$sort": {"cnt": -1}},
        {"$limit": 10}
    ]
    mongo_stats = list(db.book_ratings.aggregate(pipeline))
    client.close()

    conn = get_sql_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT ISBN, AVG(book_rating) as avg, COUNT(*) as cnt FROM ratings GROUP BY ISBN ORDER BY cnt DESC LIMIT 10;")
    sql_stats = cur.fetchall()
    cur.close(); conn.close()

    print("Mongo (top 10 by count):")
    pp.pprint(mongo_stats)
    print("SQL (top 10 by count):")
    pp.pprint(sql_stats)
    print("[Hybrid] Nota: divergências podem surgir se writes ocorrerem simultaneamente nas duas fontes.")

# -----------------------
# Execução orquestrada dos testes adaptados ao projeto
# -----------------------
def run_all_project_scenarios():
    print("=== Preparando ambiente de demonstração (contexto: books/ratings/users) ===")
    prepare_demo_sql_tables()
    prepare_demo_mongo_collections()

    print("\n=== EXPLAINs e planos ===")
    explain_mysql("""
        SELECT b.ISBN, b.book_title, AVG(r.book_rating) AS avg_rating, COUNT(*) AS cnt
        FROM books b
        JOIN ratings r ON r.ISBN = b.ISBN
        GROUP BY b.ISBN, b.book_title
        HAVING cnt >= 5
        ORDER BY avg_rating DESC
        LIMIT 10
    """)
    explain_mongo("book_ratings", {"ISBN": "0195153448"})

    # MySQL scenarios
    print("\n=== Cenários MySQL ===")
    mysql_concurrent_reads_test(concurrent_clients=6, rounds=6)
    mysql_lost_update_unsafe(iterations=3)
    mysql_lost_update_with_for_update(iterations=3)
    mysql_dirty_read_demo()
    mysql_non_repeatable_read_demo()
    mysql_phantom_read_demo()
    mysql_serializable_demo()

    # Mongo scenarios
    print("\n=== Cenários Mongo ===")
    mongo_lost_update_read_modify_write(iterations=3)
    mongo_atomic_inc_solution(iterations=3)
    mongo_transaction_demo()

    # Hybrid scenarios
    print("\n=== Cenários Híbridos ===")
    hybrid_sql_top_users_enrich_with_mongo(limit=5)
    hybrid_mongo_aggregate_compare_to_sql()

    print("\n=== Demo concluída ===")

# -----------------------
# Entrypoint
# -----------------------
if __name__ == "__main__":
    run_all_project_scenarios()
