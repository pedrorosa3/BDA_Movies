# Goal 2 - SQL Queries for Recommendation System (MySQL)

import mysql.connector

CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "<password>",
    "database": "bda_Group11",
}

def run_query(cursor, query, description):
    print(f"\n--- {description} ---")
    cursor.execute(query)
    for row in cursor.fetchall()[:10]:
        print(row)

def main():
    conn = mysql.connector.connect(**CONFIG)
    cur = conn.cursor()

    # 1 - Top 10 livros mais bem avaliados (mínimo 20 avaliações)
    query1 = """
        SELECT b.book_title, b.book_author, AVG(r.book_rating) AS avg_rating, COUNT(*) AS num_ratings
        FROM ratings r
        JOIN books b ON r.ISBN = b.ISBN
        GROUP BY b.ISBN
        HAVING COUNT(*) >= 20
        ORDER BY avg_rating DESC, num_ratings DESC
        LIMIT 10;
    """
    run_query(cur, query1, "Top 10 livros mais bem avaliados")

    # 2 - Histórico de um utilizador (exemplo user 277427)
    query2 = """
        SELECT r.book_rating, b.book_title, b.book_author
        FROM ratings r
        JOIN books b ON r.ISBN = b.ISBN
        WHERE r.user_id = 277427
        ORDER BY r.book_rating DESC;
    """
    run_query(cur, query2, "Histórico de avaliações do user 277427")

    # 3 - Autores com melhor média de classificação (mínimo 50 ratings)
    query3 = """
        SELECT b.book_author, AVG(r.book_rating) AS avg_rating, COUNT(*) AS num_ratings
        FROM ratings r
        JOIN books b ON r.ISBN = b.ISBN
        GROUP BY b.book_author
        HAVING COUNT(*) >= 50
        ORDER BY avg_rating DESC
        LIMIT 10;
    """
    run_query(cur, query3, "Top autores com melhor média de avaliação")

    # 4 - Editoras com mais avaliações
    query4 = """
        SELECT b.publisher, COUNT(r.ISBN) AS num_ratings
        FROM ratings r
        JOIN books b ON r.ISBN = b.ISBN
        GROUP BY b.publisher
        ORDER BY num_ratings DESC
        LIMIT 10;
    """
    run_query(cur, query4, "Editoras com mais avaliações")

    # 5 - Utilizadores mais ativos (para usar no Mongo)
    query5 = """
        SELECT user_id, COUNT(*) AS total_ratings
        FROM ratings
        GROUP BY user_id
        ORDER BY total_ratings DESC
        LIMIT 10;
    """
    #run_query(cur, query5, "Top 10 utilizadores mais ativos (para integração com Mongo)")

    # 8 - Recomendações colaborativas: livros não lidos pelo user 277427
    query8 = """
        SELECT b.book_title, b.book_author, AVG(r2.book_rating) AS avg_rating
        FROM ratings r1
        JOIN ratings r2 ON r1.ISBN = r2.ISBN AND r1.user_id != r2.user_id
        JOIN books b ON r2.ISBN = b.ISBN
        WHERE r1.user_id = 277427
          AND r2.ISBN NOT IN (
              SELECT ISBN FROM ratings WHERE user_id = 277427
          )
        GROUP BY b.ISBN
        HAVING COUNT(*) >= 10
        ORDER BY avg_rating DESC
        LIMIT 10;
    """
    #run_query(cur, query8, "Livros recomendados para o utilizador 277427")

    # 9 - Distribuição de ratings por ano de publicação
    query9 = """
        SELECT b.year_of_publication, 
               ROUND(AVG(r.book_rating), 2) AS avg_rating, 
               COUNT(*) AS num_ratings
        FROM ratings r
        JOIN books b ON r.ISBN = b.ISBN
        WHERE b.year_of_publication BETWEEN 1900 AND 2020
        GROUP BY b.year_of_publication
        HAVING COUNT(*) > 50
        ORDER BY b.year_of_publication;
    """
    #run_query(cur, query9, "Distribuição média de ratings por ano")
    
    # NOVA QUERY A - Top livros por número de ratings
    queryA = """
        SELECT b.ISBN, b.book_title, COUNT(*) AS num_ratings
        FROM ratings r
        JOIN books b ON r.ISBN = b.ISBN
        GROUP BY b.ISBN
        ORDER BY num_ratings DESC
        LIMIT 20;
    """
    run_query(cur, queryA, "Top livros com mais ratings (para integração Mongo)")

    # NOVA QUERY C - Lista de ISBN + média global (para enviar ao Mongo)
    queryC = """
        SELECT b.ISBN, b.book_title, AVG(r.book_rating) AS avg_rating
        FROM ratings r
        JOIN books b ON r.ISBN = b.ISBN
        GROUP BY b.ISBN
        ORDER BY avg_rating DESC
        LIMIT 50;
    """
    run_query(cur, queryC, "Top livros por média (para integração Mongo)")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
