import mysql.connector

# Configuração da ligação MySQL
CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "<password>",
}

DDL = [

    # Apagar base antiga
    "DROP DATABASE IF EXISTS bda_Group11",

    # Criar base
    """
    CREATE DATABASE IF NOT EXISTS bda_Group11
      DEFAULT CHARACTER SET utf8mb4
      DEFAULT COLLATE utf8mb4_0900_ai_ci
    """,

    "USE bda_Group11",

    # BOOKS — mantém TODAS as colunas do CSV
    """
    CREATE TABLE IF NOT EXISTS books (
      ISBN VARCHAR(20) PRIMARY KEY,
      book_title VARCHAR(255),
      book_author VARCHAR(255),
      year_of_publication INT,
      publisher VARCHAR(255),
      image_url_s TEXT,
      image_url_m TEXT,
      image_url_l TEXT
    )
    """,

    # RATINGS — user_id vem do MongoDB, por isso SEM FK
    """
    CREATE TABLE IF NOT EXISTS ratings (
      user_id INT,
      ISBN VARCHAR(20),
      book_rating INT,
      PRIMARY KEY (user_id, ISBN),
      FOREIGN KEY (ISBN) REFERENCES books(ISBN)
        ON UPDATE CASCADE ON DELETE CASCADE
    )
    """
]


def main():
    conn = mysql.connector.connect(**CONFIG)
    cur = conn.cursor()

    for stmt in DDL:
        cur.execute(stmt)

    conn.commit()
    cur.close()
    conn.close()
    print("Base de dados e tabelas criadas com sucesso (bda_Group11).")


if __name__ == "__main__":
    main()
