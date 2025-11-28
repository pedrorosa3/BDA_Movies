from pymongo import MongoClient
import mysql.connector
from config import Config

# Função utilitária
def show(title):
    print("\n" + "="*60)
    print(">>> " + title)
    print("="*60)

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

    # ============================================================
    # 1) SQL → Top livros / Mongo → Utilizadores que os avaliaram
    # ============================================================
    show("1) Top 5 livros por média (SQL) + users que os avaliaram (Mongo)")
    
    query_top_books = """
        SELECT b.ISBN, b.book_title, ROUND(AVG(r.book_rating),2) AS avg_rating
        FROM ratings r
        JOIN books b ON r.ISBN = b.ISBN
        GROUP BY b.ISBN
        HAVING COUNT(*) >= 30
        ORDER BY avg_rating DESC
        LIMIT 5;
    """
    cur.execute(query_top_books)
    top_books = cur.fetchall()

    print("\nTop livros:")
    for book in top_books:
        print(book)

    # Agora usar estes ISBN no Mongo
    for book in top_books:
        isbn = book["ISBN"]
        mongo_doc = db.book_ratings.find_one({"ISBN": isbn}, {"_id":0})
        print(f"\nRatings embutidos deste livro ({isbn}):")
        if mongo_doc:
            print(mongo_doc)
        else:
            print("Sem ratings no Mongo.")

    # ============================================================
    # 2) SQL → Users mais ativos / Mongo → Dados destes users
    # ============================================================
    show("2) Top 10 utilizadores mais ativos (SQL) + info deles (Mongo)")

    query_users_active = """
        SELECT user_id, COUNT(*) as total_ratings
        FROM ratings
        GROUP BY user_id
        ORDER BY total_ratings DESC
        LIMIT 10;
    """
    cur.execute(query_users_active)
    active_users = cur.fetchall()

    for user in active_users:
        print("\nUser SQL:", user)
        mongo_user = db.users.find_one({"user_id": user["user_id"]}, {"_id":0})
        print("User Mongo:", mongo_user)

    # ============================================================
    # 3) Mongo → users idade 20–30 / SQL → livros mais avaliados por eles
    # ============================================================
    show("3) Users com idade 20–30 (Mongo) + livros mais avaliados por eles (SQL)")

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
    cur.execute(query)
    authors = cur.fetchall()

    for a in authors:
        print("\nAutor:", a)

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
