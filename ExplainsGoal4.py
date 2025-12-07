"""
Grupo 11
Diogo Sousa - 60250; 
Francisco Lopes - 60252;  
Guilherme Almeida - 60264;
Pedro Rosa  - 60294
"""

import mysql.connector
from config import Config

# ============================================================
# Ligação ao MySQL
# ============================================================
def get_sql_connection():
    return mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )


# ============================================================
# Função EXPLAIN
# ============================================================
def explain(query, params=None, label="EXPLAIN"):
    conn = get_sql_connection()
    cur = conn.cursor(dictionary=True)

    print("\n" + "=" * 100)
    print(label)
    print("=" * 100)

    try:
        cur.execute("EXPLAIN " + query, params or ())
        rows = cur.fetchall()

        # Cabeçalho formatado
        print(f"{'table':<15} {'type':<12} {'rows':<10} {'key':<30} {'Extra'}")
        print("-" * 100)

        for row in rows:
            table = str(row.get("table", ""))         
            typ = str(row.get("type", ""))             
            rows_count = str(row.get("rows", ""))      
            key = str(row.get("key", ""))              
            extra = str(row.get("Extra", ""))          

            print(f"{table:<15} {typ:<12} {rows_count:<10} {key:<30} {extra}")

    finally:
        cur.close()
        conn.close()




# ============================================================
# Queries SQL do GOAL 2 
# ============================================================
Q2_QUERY1 = """
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

Q2_QUERY2 = """
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

Q2_QUERY3 = """
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

# ============================================================
# Queries SQL do GOAL 4 
# ============================================================
Q4_QUERY1 = """
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

Q4_QUERY2 = """
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

Q4_QUERY3 = """
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


# ============================================================
# MAIN — COMPARAÇÃO QUERY A QUERY
# ============================================================
def main():
    
    print("\n============================================================")
    print("                 COMPARAÇÃO QUERY A QUERY                   ")
    print("============================================================")

    # --------------------------------------------------------
    # QUERY 1 — TOP 10 POR RATING
    # --------------------------------------------------------
    
    explain(Q2_QUERY1, label="GOAL 2 — Query 1 (Original) — Top 10 por rating")
    explain(Q4_QUERY1, label="GOAL 4 — Query 1 (Otimizada) — Top 10 por rating")

    # --------------------------------------------------------
    # QUERY 2 — LIVROS MAIS POPULARES
    # --------------------------------------------------------
    explain(Q2_QUERY2, params=(10,), label="GOAL 2 — Query 2 (Original) — Livros populares")
    explain(Q4_QUERY2, params=(10,), label="GOAL 4 — Query 2 (Otimizada) — Livros populares")

    # --------------------------------------------------------
    # QUERY 3 — SELF JOIN LIVROS DO MESMO AUTOR
    # --------------------------------------------------------
    explain(Q2_QUERY3, params=(20,), label="GOAL 2 — Query 3 (Original) — Self-Join autor")
    explain(Q4_QUERY3, params=(20,), label="GOAL 4 — Query 3 (Otimizada) — Self-Join autor")


if __name__ == "__main__":
    main()
