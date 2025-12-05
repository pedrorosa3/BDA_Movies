import time
import pprint
import sys
from typing import List, Dict, Any

import mysql.connector
from mysql.connector import Error as MySQLError
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from config import Config

import ScriptGoal2_Integrated

# ============================================================
# LIGAÇÃO
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
#  Remover indices antigos, caso existam
# ============================================================

def drop_all_mysql_indexes():
    """
    Remove TODOS os índices não obrigatórios de TODAS as tabelas do MySQL
    (exclui PRIMARY KEY, UNIQUE, FOREIGN KEY).
    """
    conn = get_sql_connection()
    cur = conn.cursor(dictionary=True)

    print("\n[MySQL] Removendo TODOS os índices (exceto PK, FK, UNIQUE)...")

    try:
        # Obtém todas as tabelas da BD
        cur.execute("SHOW TABLES")
        tabelas = [list(row.values())[0] for row in cur.fetchall()]

        for tabela in tabelas:
            print(f"\n  > Tabela: {tabela}")

            # Lista detalhada dos índices
            cur.execute(f"SHOW INDEX FROM {tabela}")
            idxs = cur.fetchall()

            # Detetar UNIQUE/PRIMARY para não remover
            for idx in idxs:
                nome = idx["Key_name"]
                tipo = idx["Index_type"]
                non_unique = idx["Non_unique"]  # 0 = UNIQUE ou PRIMARY

                # ignorar PK, UK e índices criados automaticamente
                if nome == "PRIMARY" or non_unique == 0:
                    continue

                print(f"    - DROP INDEX {nome}")
                try:
                    cur.execute(f"DROP INDEX `{nome}` ON `{tabela}`")
                except MySQLError as e:
                    print(f"      (erro a remover {nome}): {e}")

        conn.commit()
    finally:
        cur.close()
        conn.close()
        
def drop_all_mongo_indexes():
    """
    Remove TODOS os índices de TODAS as coleções do MongoDB,
    exceto o índice obrigatório '_id_'.
    """
    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    print("\n[MongoDB] Removendo TODOS os índices (exceto _id_)...")

    try:
        colecoes = db.list_collection_names()
        for coll_name in colecoes:
            coll = db[coll_name]
            print(f"\n  > Coleção: {coll_name}")

            for idx in coll.list_indexes():
                nome = idx["name"]
                if nome == "_id_":
                    continue

                print(f"    - dropIndex {nome}")
                coll.drop_index(nome)

    finally:
        client.close()

# ============================================================
#  CRIAÇÃO DE ÍNDICES (MySQL + MongoDB)
# ============================================================

def create_mysql_indexes():
    """
    Garante a existência de índices relevantes para as queries.

    TIPOS DE INDEXAÇÃO USADOS:
      - Índices simples (single-column index)
      - Índices compostos (multi-column index)
    """

    index_statements = [
        # --------------------------
        # Tabela ratings
        # --------------------------
        # Index simples em ISBN para acelerar GROUP BY/WHERE por ISBN.
        ("idx_ratings_isbn",
         "CREATE INDEX idx_ratings_isbn ON ratings (ISBN)"),

        # Index simples em user_id para acelerar WHERE user_id IN (...)
        ("idx_ratings_user",
         "CREATE INDEX idx_ratings_user ON ratings (user_id)"),

        # Índice composto para queries que filtram por (user_id, ISBN)
        # e para facilitar possíveis joins/condições em ambas as colunas.
        ("idx_ratings_user_isbn",
         "CREATE INDEX idx_ratings_user_isbn ON ratings (user_id, ISBN)"),

        # Índice composto para suportar agregações por ISBN e ranking
        # por book_rating (cobre a query de média de rating).
        ("idx_ratings_isbn_rating",
         "CREATE INDEX idx_ratings_isbn_rating ON ratings (ISBN, book_rating)"),
    ]

    conn = get_sql_connection()
    cur = conn.cursor()

    print("\n[MySQL] A criar/garantir índices...")

    try:
        for idx_name, stmt in index_statements:
            try:
                print(f"  - Criando índice {idx_name} ...")
                cur.execute(stmt)
            except MySQLError as e:
                # 1061 = Duplicate key name
                if getattr(e, "errno", None) == 1061:
                    print(f"    > Índice {idx_name} já existe, a ignorar.")
                else:
                    print(f"    > Erro ao criar índice {idx_name}: {e}")
                    raise
        conn.commit()
    finally:
        cur.close()
        conn.close()


def create_mongo_indexes():
    """
    Garante índices nas coleções MongoDB usadas.
    TIPOS DE INDEXAÇÃO USADOS:
      - Índices simples
      - Índices compostos
      - Índices multikey (por estarem em arrays)
    """
    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    print("\n[MongoDB] A criar/garantir índices...")

    try:
        # --------------------------
        # Coleção book_ratings
        # Estrutura esperada: { ISBN, ratings: [ { user_id, rating, ... } ] }
        # --------------------------
        print("  - book_ratings: índice simples em ISBN")
        db.book_ratings.create_index(
            [("ISBN", 1)],
            name="idx_book_ratings_isbn"
        )

        print("  - book_ratings: índice multikey em ratings.user_id")
        db.book_ratings.create_index(
            [("ratings.user_id", 1)],
            name="idx_book_ratings_ratings_user_id"
        )

        print("  - book_ratings: índice composto (ISBN, ratings.user_id)")
        db.book_ratings.create_index(
            [("ISBN", 1), ("ratings.user_id", 1)],
            name="idx_book_ratings_isbn_user_composto"
        )

        # --------------------------
        # Coleção users
        # Estrutura esperada: { user_id, location, ... }
        # --------------------------
        print("  - users: índice simples em location")
        db.users.create_index(
            [("location", 1)],
            name="idx_users_location"
        )

        print("  - users: índice composto (location, user_id)")
        db.users.create_index(
            [("location", 1), ("user_id", 1)],
            name="idx_users_location_user_composto"
        )

    finally:
        client.close()

# ============================================================
#  QUERIES OTIMIZADAS (mesma lógica + suportadas pelos índices)
# ============================================================

def sql_top10_livros_por_rating_otimizado() -> List[Dict[str, Any]]:
    """
    SQL OTIMIZADO #1 — Top 10 livros pela média de rating.

    Otimizações:
      - Em vez de dois subselects agregados, usamos UMA agregação
        sobre ratings JOIN books, reduzindo passes na tabela.
      - Índice composto ratings(ISBN, book_rating) ajuda o GROUP BY
        e o cálculo de AVG(book_rating) por ISBN.
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
        ) c ON c.ISBN = b.ISBN
        JOIN (
            SELECT ISBN, AVG(book_rating) AS avg_rating
            FROM ratings
            GROUP BY ISBN
        ) a ON a.ISBN = b.ISBN
        WHERE c.total_ratings > 10
        ORDER BY a.avg_rating DESC
        LIMIT 10;
    """

    try:
        cur.execute(query)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def sql_top_livros_populares_otimizado(limit=10) -> List[Dict[str, Any]]:
    """
    SQL OTIMIZADO #2 — Top livros mais populares.

    Otimizações:
      - Primeiro agregamos apenas em ratings (com índice em ISBN),
        limitando o nº de linhas, e só depois fazemos JOIN com books.
      - Isto pode reduzir muito o custo se ratings for muito grande.
    """
    conn = get_sql_connection()
    cur = conn.cursor(dictionary=True)

    query = """
        SELECT
            b.ISBN,
            b.book_title,
            r_tot.total_ratings
        FROM (
            SELECT
                ISBN,
                COUNT(*) AS total_ratings
            FROM ratings
            GROUP BY ISBN
            ORDER BY total_ratings DESC
            LIMIT %s
        ) AS r_tot
        JOIN books b ON b.ISBN = r_tot.ISBN
        ORDER BY r_tot.total_ratings DESC;
    """

    try:
        cur.execute(query, (limit,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def sql_livros_mesmo_autor_otimizado(limit=20) -> List[Dict[str, Any]]:
    """
    SQL OTIMIZADO #3 — Self-Join (b1, b2) pelo mesmo autor.

    Otimizações:
      - Índices em (book_author, ISBN) reduzem o custo do self-join.
      - Excluímos autores NULL para evitar pares desnecessários.
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
        WHERE b1.book_author IS NOT NULL
        ORDER BY author
        LIMIT %s;
    """

    try:
        cur.execute(query, (limit,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def mongo_top_users_otimizado(limit=10) -> List[Dict[str, Any]]:
    """
    Mongo OTIMIZADO — Top users por nº de ratings.

    A pipeline é equivalente à original, mas:
      - Agora beneficia do índice multikey em ratings.user_id,
        acelerando o $unwind + $group.
    """
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


def mongo_top_localizacoes_otimizado(limit=10) -> List[Dict[str, Any]]:
    """
    Mongo OTIMIZADO — Top localizações com mais utilizadores.

    Continua equivalente, mas:
      - Passa a usar índices em users.location e (location, user_id).
    """
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


def hibrido_localizacoes_com_atividade_otimizado(limit=10) -> List[Dict[str, Any]]:
    """
    Híbrido OTIMIZADO #1:

    Diferenças vs original:
      - Em vez de fazer 1 query SQL por localização, fazemos:
          * 1 query Mongo para todos os users das top localizações
          * 1 query SQL para todos esses users de uma só vez
        e depois agregamos em Python por localização.

      - Isto reduz drasticamente o nº de chamadas SQL.
      - Índice ratings(user_id) e índices em Mongo users(location, user_id)
        ajudam bastante.
    """
    # Top localizações (já aproveita os índices em Mongo)
    top_loc = mongo_top_localizacoes_otimizado(limit=limit)
    top_locations = [l["location"] for l in top_loc]

    mongo_client = get_mongo_client()
    mongo_db = mongo_client[Config.MONGO_DB]

    # 1) Buscar TODOS os users de TODAS as localizações relevantes
    users_cursor = mongo_db.users.find(
        {"location": {"$in": top_locations}},
        {"_id": 0, "user_id": 1, "location": 1}
    )
    users = list(users_cursor)

    # Mapear user_id -> location e também lista de user_ids por location
    user_to_location = {}
    location_to_user_ids = {loc: [] for loc in top_locations}

    for u in users:
        uid = u["user_id"]
        loc = u["location"]
        user_to_location[uid] = loc
        location_to_user_ids[loc].append(uid)

    all_user_ids = list(user_to_location.keys())

    if not all_user_ids:
        # Sem utilizadores encontrados, devolvemos zero ratings para todas as localizações
        mongo_client.close()
        return [
            {
                "location": l["location"],
                "mongo_users": l["num_users"],
                "sql_total_ratings": 0
            }
            for l in top_loc
        ]

    # 2) Uma única query SQL para todos os users
    conn = get_sql_connection()
    cur = conn.cursor(dictionary=True)

    try:
        placeholders = ",".join(["%s"] * len(all_user_ids))
        query = f"""
            SELECT user_id, COUNT(*) AS total_ratings
            FROM ratings
            WHERE user_id IN ({placeholders})
            GROUP BY user_id;
        """
        cur.execute(query, tuple(all_user_ids))
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()
        mongo_client.close()

    # 3) Agregamos total_ratings por localização em Python
    location_totals = {loc: 0 for loc in top_locations}
    for r in rows:
        uid = r["user_id"]
        total = int(r["total_ratings"])
        loc = user_to_location.get(uid)
        if loc is not None:
            location_totals[loc] += total

    resultados = []
    for loc_info in top_loc:
        loc = loc_info["location"]
        resultados.append({
            "location": loc,
            "mongo_users": loc_info["num_users"],
            "sql_total_ratings": location_totals.get(loc, 0)
        })

    return resultados


def hibrido_livros_populares_com_users_otimizado(limit=10) -> List[Dict[str, Any]]:
    """
    Híbrido OTIMIZADO #2:

      - Usa sql_top_livros_populares_otimizado() em vez da versão original,
        beneficiando de índices em ratings(ISBN).
      - Pipeline Mongo permanece eficiente com índices em ISBN e ratings.user_id.
    """
    top_sql = sql_top_livros_populares_otimizado(limit=limit)
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
#  UTILITÁRIO DE MEDIÇÃO DE TEMPO
# ============================================================

def medir_tempo(func, *args, n_runs: int = 1, label: str | None = None):
    """
    Executa uma função N vezes e devolve (resultado_da_ultima_execução, tempo_médio).
    Imprime também o tempo na consola.
    """
    inicio = time.perf_counter()
    result = None
    for _ in range(n_runs):
        result = func(*args)
    fim = time.perf_counter()
    duracao = (fim - inicio) / n_runs
    nome = label or func.__name__
    print(f" - {nome}: {duracao:.4f} segundos (média de {n_runs} execuções)")
    return result, duracao


# ============================================================
#  MAIN — corre tudo e compara ANTES vs DEPOIS
# ============================================================

def main():
    pp = pprint.PrettyPrinter(indent=2)
    
    print("\n====================================================")
    print("    REMOÇÃO TOTAL DE ÍNDICES (MySQL + MongoDB)      ")
    print("====================================================")
    drop_all_mysql_indexes()
    drop_all_mongo_indexes()

    print("\n====================================================")
    print("        BENCHMARK ANTES (QUERIES ORIGINAIS)        ")
    print("====================================================")

    
    n_runs = 4

    base_sql_top10, t1 = medir_tempo(
        ScriptGoal2_Integrated.sql_top10_livros_por_rating,
        n_runs=n_runs,
        label="SQL ORIGINAL → Top 10 livros por rating"
    )
    base_sql_pop, t2 = medir_tempo(
        ScriptGoal2_Integrated.sql_top_livros_populares,
        10, n_runs=n_runs,
        label="SQL ORIGINAL → Livros mais populares"
    )
    base_sql_self, t3 = medir_tempo(
        ScriptGoal2_Integrated.sql_livros_mesmo_autor,
        20, n_runs=n_runs,
        label="SQL ORIGINAL → Livros do mesmo autor (self-join)"
    )
    base_m_top_users, t4 = medir_tempo(
        ScriptGoal2_Integrated.mongo_top_users,
        10, n_runs=n_runs,
        label="Mongo ORIGINAL → Top users"
    )
    base_m_top_loc, t5 = medir_tempo(
        ScriptGoal2_Integrated.mongo_top_localizacoes,
        10, n_runs=n_runs,
        label="Mongo ORIGINAL → Top localizações"
    )
    base_h1, t6 = medir_tempo(
        ScriptGoal2_Integrated.hibrido_localizacoes_com_atividade,
        10, n_runs=n_runs,
        label="Híbrido ORIGINAL → Localizações + atividade SQL"
    )
    base_h2, t7 = medir_tempo(
        ScriptGoal2_Integrated.hibrido_livros_populares_com_users,
        10, n_runs=n_runs,
        label="Híbrido ORIGINAL → Livros populares + users Mongo"
    )

    print("\nExemplo de resultados da query SQL ORIGINAL (Top 10 por rating):")
    pp.pprint(base_sql_top10[:3])

    # --------------------------------------------------------
    # Criar índices (pode ser executado apenas uma vez)
    # --------------------------------------------------------
    print("\n====================================================")
    print("        CRIAÇÃO / GARANTIA DE ÍNDICES               ")
    print("====================================================")
    create_mysql_indexes()
    create_mongo_indexes()

    # --------------------------------------------------------
    # MEDIÇÃO DEPOIS (OTIMIZADO + ÍNDICES)
    # --------------------------------------------------------
    print("\n====================================================")
    print("        BENCHMARK DEPOIS (OTIMIZADO + ÍNDICES)      ")
    print("====================================================")

    opt_sql_top10, t1o = medir_tempo(
        sql_top10_livros_por_rating_otimizado,
        n_runs=n_runs,
        label="SQL OTIMIZADO → Top 10 livros por rating"
    )
    opt_sql_pop, t2o = medir_tempo(
        sql_top_livros_populares_otimizado,
        10, n_runs=n_runs,
        label="SQL OTIMIZADO → Livros mais populares"
    )
    opt_sql_self, t3o = medir_tempo(
        sql_livros_mesmo_autor_otimizado,
        20, n_runs=n_runs,
        label="SQL OTIMIZADO → Livros do mesmo autor (self-join)"
    )
    opt_m_top_users, t4o = medir_tempo(
        mongo_top_users_otimizado,
        10, n_runs=n_runs,
        label="Mongo OTIMIZADO → Top users"
    )
    opt_m_top_loc, t5o = medir_tempo(
        mongo_top_localizacoes_otimizado,
        10, n_runs=n_runs,
        label="Mongo OTIMIZADO → Top localizações"
    )
    opt_h1, t6o = medir_tempo(
        hibrido_localizacoes_com_atividade_otimizado,
        10, n_runs=n_runs,
        label="Híbrido OTIMIZADO → Localizações + atividade SQL"
    )
    opt_h2, t7o = medir_tempo(
        hibrido_livros_populares_com_users_otimizado,
        10, n_runs=n_runs,
        label="Híbrido OTIMIZADO → Livros populares + users Mongo"
    )

    print("\nExemplo de resultados da query SQL OTIMIZADA (Top 10 por rating):")
    pp.pprint(opt_sql_top10[:3])

   
    print("\n====================================================")
    print("                    RESUMO                          ")
    print(" (tempo em segundos; valores menores são melhores)  ")
    print("====================================================")
    linhas = [
        ("SQL Top10 rating", t1, t1o),
        ("SQL Populares", t2, t2o),
        ("SQL Self-Join autor", t3, t3o),
        ("Mongo Top users", t4, t4o),
        ("Mongo Top locais", t5, t5o),
        ("Híbrido Loc+Activity", t6, t6o),
        ("Híbrido Livros+Users", t7, t7o),
    ]
    for nome, tb, to in linhas:
        ganho = ((tb - to) / tb) * 100 if tb and to else 0.0
        print(f"{nome:26s}  ANTES={tb:.4f}  DEPOIS={to:.4f}  SPEED UP≈{ganho:.4f}")


if __name__ == "__main__":
    main()
