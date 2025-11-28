from pymongo import MongoClient
import mysql.connector
from config import Config


# ============================================================
# MAIN
# ============================================================
def main():
    # ------------------------------
    # Abrir conexões
    # ------------------------------
    conn = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )
    cur = conn.cursor(dictionary=True)    

    mongo_client = MongoClient(Config.build_mongo_uri())
    db = mongo_client[Config.MONGO_DB]

def get_mongo_client():
    """Cria ligação ao MongoDB e devolve o cliente."""
    try:
        return MongoClient(MONGO_URI)
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

    # Agora usar estes ISBN no Mongo
    for book in top_books:
        isbn = book["ISBN"]
        mongo_doc = db.book_ratings.find_one({"ISBN": isbn}, {"_id":0})
        print(f"\nRatings embutidos deste livro ({isbn}):")
        if mongo_doc:
            print(mongo_doc)
        else:
            print("Sem ratings no Mongo.")

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

    for user in active_users:
        print("\nUser SQL:", user)
        mongo_user = db.users.find_one({"user_id": user["user_id"]}, {"_id":0})
        print("User Mongo:", mongo_user)


    users_age_20_30 = list(db.users.find(
        {"age": {"$gte": 20, "$lte": 30}},
        {"user_id": 1, "_id": 0}
    ))

    user_ids = tuple([u["user_id"] for u in users_age_20_30])

    print(f"Total users 20-30 anos no Mongo: {len(user_ids)}")

    if len(user_ids) > 0:
        query_young_books = f"""
            SELECT b.book_title, COUNT(*) AS num_ratings, ROUND(AVG(r.book_rating),2) AS avg_rating
            FROM ratings r
            JOIN books b ON r.ISBN = b.ISBN
            WHERE r.user_id IN {user_ids}
            GROUP BY b.ISBN
            HAVING COUNT(*) >= 15
            ORDER BY avg_rating DESC
            LIMIT 10;
        """
        cur.execute(query_young_books)
        top_young_books = cur.fetchall()
        for row in top_young_books:
            print(row)
    else:
        print("Nenhum user entre 20 e 30 anos encontrado.")

    # ============================================================
    # 4) SQL → livros mais populares / Mongo → ratings embutidos
    # ============================================================
    show("4) Livros mais populares (SQL) + análise rápida dos ratings Mongo")

    query_popular = """
        SELECT ISBN, COUNT(*) AS total_ratings
        FROM ratings
        GROUP BY ISBN
        ORDER BY total_ratings DESC
        LIMIT 5;
    """
    cur.execute(query_popular)
    most_rated = cur.fetchall()

    for row in most_rated:
        print("\nLivro popular (SQL):", row)
        mongo_data = db.book_ratings.find_one({"ISBN": row["ISBN"]}, {"_id":0})
        #print("Ratings no Mongo:", mongo_data)
        
        
    # ============================================================
    # 5) 
    # ============================================================
    show("5) Autores mais bem avaliados (SQL) + Perfil dos leitores (Mongo)")

    query = """
        SELECT b.book_author, COUNT(*) AS total_ratings, ROUND(AVG(r.book_rating), 2) AS avg_rating
        FROM ratings r
        JOIN books b ON r.ISBN = b.ISBN
        GROUP BY b.book_author
        HAVING total_ratings >= 30
        ORDER BY avg_rating DESC
        LIMIT 5;
    """
    client = get_mongo_client()
    db = client[MONGO_DB]

    pipeline = [
        {"$unwind": "$ratings"},  # separa cada rating num documento independente
        {"$group": {"_id": "$ratings.user_id", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}},
        {"$limit": limit},
        {"$project": {"user_id": "$_id", "total": 1, "_id": 0}},
    ]

        # Obter users que avaliaram livros deste autor
        cur.execute("""
            SELECT DISTINCT r.user_id
            FROM ratings r
            JOIN books b ON r.ISBN = b.ISBN
            WHERE b.book_author = %s
        """, (a["book_author"],))

        sql_users = [u["user_id"] for u in cur.fetchall()]

        profiles = list(db.users.find(
            {"user_id": {"$in": sql_users}},
            {"_id": 0}
        ))

        print("Perfis dos leitores (Mongo):", profiles)


 
    # ------------------------------
    # Fechar conexões
    # ------------------------------
    cur.close()
    conn.close()
    mongo_client.close()
    print("\n\Queries concluídas!\n")


if __name__ == "__main__":
    main()

