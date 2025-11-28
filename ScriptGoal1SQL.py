import mysql.connector

# --------------------------------------------------------------
# Configuração da ligação MySQL (não inclui database porque a BD
# ainda não existe neste momento — será criada no DDL).
# --------------------------------------------------------------
CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "<password>",
}

# --------------------------------------------------------------
# DDL — conjunto de comandos SQL para criar a base de dados
# e as respetivas tabelas de forma limpa e consistente.
# Cada string é executada sequencialmente.
# --------------------------------------------------------------
DDL = [

    "DROP DATABASE IF EXISTS bda_Group11",  
    # Apaga a BD antiga (se existir) → evita conflitos com dados ou esquemas antigos.

    """
    CREATE DATABASE IF NOT EXISTS bda_Group11
      DEFAULT CHARACTER SET utf8mb4        -- Suporta todos os caracteres Unicode (incl. emojis)
      DEFAULT COLLATE utf8mb4_0900_ai_ci   -- Collation moderno; melhor ordenação e comparação
    """,

    "USE bda_Group11",  
    # Seleciona a BD recém-criada para criar as tabelas seguintes.

    # ----------------------------------------------------------
    # Tabela BOOKS — réplica fiel do CSV original.
    # ISBN é PRIMARY KEY pois identifica unicamente cada livro.
    # ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS books (
      ISBN VARCHAR(20) PRIMARY KEY,        -- Identificação única do livro
      book_title TEXT,                     -- Título completo do livro
      book_author TEXT,                    -- Nome do autor
      year_of_publication INT,             -- Ano de publicação
      publisher TEXT,                      -- Editora
      image_url_s TEXT,                    -- Link imagem pequena
      image_url_m TEXT,                    -- Link imagem média
      image_url_l TEXT                     -- Link imagem grande
    )
    """,

    # ----------------------------------------------------------
    # Tabela RATINGS — liga utilizadores (MongoDB) a livros.
    # user_id NÃO tem FK porque é importado de MongoDB.
    # ISBN TEM FK → referência à tabela books.
    #
    # ON UPDATE CASCADE:
    #   Se um ISBN mudar em books (situação rara mas possível),
    #   a mudança propaga-se para ratings automaticamente.
    #
    # ON DELETE CASCADE:
    #   Se um livro for apagado da tabela books,
    #   TODAS as ratings associadas também são apagadas.
    #   Isto mantém integridade e evita órfãos.
    # ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS ratings (
      user_id INT,                         -- ID do utilizador (vem do MongoDB; sem FK)
      ISBN VARCHAR(20),                    -- ISBN do livro
      book_rating INT,                     -- Classificação dada por um utilizador
      PRIMARY KEY (user_id, ISBN),         -- Garante que 1 utilizador classifica 1 livro apenas 1 vez
      FOREIGN KEY (ISBN) REFERENCES books(ISBN) 
        ON UPDATE CASCADE                  -- Propaga alterações no ISBN
        ON DELETE CASCADE                  -- Apaga ratings associadas a livros removidos
    )
    """
]


# --------------------------------------------------------------
# Função principal:
#   - liga ao MySQL
#   - executa cada comando DDL
#   - fecha a ligação
# --------------------------------------------------------------
def main():
    conn = mysql.connector.connect(**CONFIG)
    cur = conn.cursor()

    for stmt in DDL:
        cur.execute(stmt)  # executa cada comando SQL sequencialmente

    conn.commit()  # confirma todas as alterações
    cur.close()
    conn.close()
    print("Base de dados e tabelas criadas com sucesso (bda_Group11).")


# --------------------------------------------------------------
# Entry point do script
# --------------------------------------------------------------
if __name__ == "__main__":
    main()