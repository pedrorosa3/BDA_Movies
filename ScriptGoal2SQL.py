# Goal 2 - SQL Queries for Recommendation System (MySQL)
# ------------------------------------------------------
# Este script executa queries para extrair informações úteis para o sistema de recomendações.


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
    for row in cursor.fetchall()[:10]:  # limitar a 10 resultados para legibilidade
        print(row)

def main():
    conn = mysql.connector.connect(**CONFIG)
    cur = conn.cursor()

    # 1️ - Top 10 livros mais bem avaliados (mínimo 20 avaliações)
    # Mostra os livros com melhor média de classificação
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

    # 2️ - Histórico de avaliações de um utilizador específico
    # Substituir o user_id pelo desejado (exemplo: 277427) ## Esta query deve de ser melhorada
    query2 = """
        SELECT r.book_rating, b.book_title, b.book_author
        FROM ratings r
        JOIN books b ON r.ISBN = b.ISBN
        WHERE r.user_id = 277427
        ORDER BY r.book_rating DESC;
    """
    run_query(cur, query2, "Histórico de avaliações do utilizador 277427")

    # 3️ - Autores com melhor média de classificação (mínimo 50 avaliações totais)
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

    # 4️ - Editoras com livros mais bem classificados
    query4 = """
        SELECT b.publisher, COUNT(r.ISBN) AS num_ratings
        FROM ratings r
        JOIN books b ON r.ISBN = b.ISBN
        GROUP BY b.publisher
        ORDER BY num_ratings DESC
        LIMIT 10;
    """
    run_query(cur, query4, "Editoras com mais avaliações")

    # 5️ - Query combinada (MySQL + MongoDB)
    # Nesta query, extraímos os IDs dos utilizadores mais ativos em MySQL,
    # que depois serão usados no script do MongoDB para cruzar com preferências. 
    query5 = """
        SELECT user_id, COUNT(*) AS total_ratings
        FROM ratings
        GROUP BY user_id
        ORDER BY total_ratings DESC
        LIMIT 10;
    """
    run_query(cur, query5, "Top 10 utilizadores mais ativos (para integração com MongoDB)")
    
    # 6️ - Top livros por faixa etária
    # Divide os utilizadores por grupos etários e mostra os livros mais bem avaliados por grupo.
    query6 = """
        SELECT 
            CASE 
                WHEN u.age < 20 THEN '<20'
                WHEN u.age BETWEEN 20 AND 40 THEN '20-40'
                WHEN u.age BETWEEN 41 AND 60 THEN '41-60'
                ELSE '>60'
            END AS faixa_etaria,
            b.book_title,
            ROUND(AVG(r.book_rating), 2) AS avg_rating,
            COUNT(*) AS num_ratings
        FROM ratings r
        JOIN users u ON r.user_id = u.user_id
        JOIN books b ON r.ISBN = b.ISBN
        WHERE u.age IS NOT NULL
        GROUP BY faixa_etaria, b.ISBN
        HAVING COUNT(*) >= 10
        ORDER BY faixa_etaria, avg_rating DESC
        LIMIT 30;
    """
    run_query(cur, query6, "Top livros por faixa etária")

    # 7️ - Utilizadores com gostos semelhantes (simples)
    # Encontra pares de utilizadores que deram ratings idênticos ao mesmo livro.
    query7 = """
        SELECT 
            r1.user_id AS user_a,
            r2.user_id AS user_b,
            COUNT(*) AS livros_em_comum
        FROM ratings r1
        JOIN ratings r2 ON r1.ISBN = r2.ISBN 
                        AND r1.user_id < r2.user_id
                        AND ABS(r1.book_rating - r2.book_rating) <= 1
        GROUP BY user_a, user_b
        HAVING COUNT(*) >= 5
        ORDER BY livros_em_comum DESC
        LIMIT 10;
    """
    run_query(cur, query7, "Pares de utilizadores com gostos semelhantes")

    # 8️ - Livros não lidos mas recomendados (simples abordagem colaborativa)
    # Sugere livros que um utilizador ainda não leu, mas que são bem avaliados por utilizadores semelhantes.
    # Exemplo com o utilizador 277427.
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
    run_query(cur, query8, "Livros recomendados para o utilizador 277427 (ainda não lidos)")

    # 9️ - Distribuição de ratings por ano de publicação
    # Mostra a média de classificação e o número de livros avaliados por ano.
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
    run_query(cur, query9, "Distribuição média de ratings por ano de publicação")

    # 10 - Autores mais populares entre jovens (<25 anos)
    # Mostra os autores mais avaliados por utilizadores jovens.
    query10 = """
        SELECT b.book_author, COUNT(*) AS num_ratings, ROUND(AVG(r.book_rating), 2) AS avg_rating
        FROM ratings r
        JOIN users u ON r.user_id = u.user_id
        JOIN books b ON r.ISBN = b.ISBN
        WHERE u.age < 25
        GROUP BY b.book_author
        HAVING COUNT(*) >= 20
        ORDER BY num_ratings DESC, avg_rating DESC
        LIMIT 10;
    """
    run_query(cur, query10, "Autores mais populares entre jovens (<25 anos)")


    cur.close()
    conn.close()

if __name__ == "__main__":
    main()

