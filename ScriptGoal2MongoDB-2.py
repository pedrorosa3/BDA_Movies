# ScriptGoal2_MongoDB.py
# --------------------------------------------------
# Goal 2 - MongoDB Queries for Recommendation System
# Base de dados: bda_Group11
#
# Assumimos o seguinte esquema (já criado por ti no Goal 1):
#   - db.users: { user_id:int, location?:str, age?:int }
#   - db.books: {
#         ISBN:str, book_title?:str, book_author?:str, year_of_publication?:int,
#         publisher?:str, image_url_s?:str, image_url_m?:str, image_url_l?:str,
#         ratings: [ { user_id:int, book_rating:int } ]
#     }
#
# Antes de correr:
#      Verificar como queremos rodar.
#      Se local num container -> USE_LOCAL_DB = True 
#      Em caso de ATlas mudar para False e mudar o URI
#
# Conteúdo:
#   - 1) Livros com média > X (agregações)
#   - 2) Pesquisa textual por autor/título (regex)
#   - 3) Utilizadores com mais avaliações
#   - 4) Recomendações simples baseadas em items coavaliados (user-based lite)
#   - 5) Integração básica com MySQL (IDs ativos) -> detalhe de users
#   - 6) Content-based: livros semelhantes (mesmo autor/editora)
#   - 7) Preferências contextuais (filtros flexíveis)
#   - 8) Autores mais apreciados (analytics no Mongo)
#   - 9) Populares por localização (lookup users)
#   - 10) Híbrida: livros favoritos dos utilizadores mais ativos (IDs vindos do SQL)
#
# NOTA: Não tem indexação
# --------------------------------------------------

from pymongo import MongoClient
from pprint import pprint

# ---- CONFIGURAÇÕES ----
USE_LOCAL_DB = True      # True → usar Mongo local; False → usar Atlas

# ---- CONEXÃO AO MONGODB ----
if USE_LOCAL_DB:
    MONGO_USER = "root"
    MONGO_PASS = "<password>"
    MONGO_HOST = "localhost"
    MONGO_PORT = "27017"
    DB_NAME = "bda_Group11"

    LOCAL_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/"
    client = MongoClient(LOCAL_URI)
    db = client[DB_NAME]
    print("Ligação ao MongoDB local estabelecida com sucesso\n")
else:
    ATLAS_URI = "mongodb+srv://diogosfb91_db_user:<password>@cluster0.hszfcsx.mongodb.net/?appName=Cluster0"
    client = MongoClient(ATLAS_URI)
    db = client["bda_Group11"]
    print("Ligação ao MongoDB Atlas estabelecida com sucesso\n")

# Parâmetros de teste
USER_TARGET = 277427                
ISBN_TARGET = "0345417623"          
AUTHOR_DEMO = "Stephen King"        
YEAR_MIN    = 1990                  
ACTIVE_USERS_FROM_SQL = [277427, 114368, 11676,98391]  # Estes sao de teste, deveriam de vir do SQL 
# os ultimos dois tive de procurar para a ultima query ter resultados

# === HELPERS ===
def show_section(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def show_results(docs, desc: str, limit: int = 10):
    print(f"\n--- {desc} ---")
    if not docs:
        print("(sem resultados)")
        return
    for i, d in enumerate(docs[:limit], 1):
        print(f"[{i}] ", end="")
        pprint(d)
        
        
        
def main():
    # 1) Primeiros 5 utilizadores
    show_section("1) Primeiros 5 utilizadores")
    results1 = list(db.users.find().limit(5))
    show_results(results1, "Primeiros 5 utilizadores")

    # 2) Primeiro documento da coleção book_ratings
    show_section("2) Primeiro documento de book_ratings")
    results2 = [db.book_ratings.find_one()]
    show_results(results2, "Primeiro documento book_ratings")

    # 3) Ratings de um ISBN específico (usar o ISBN do results2)
    if results2 and results2[0] is not None:
        isbn_value = results2[0]["ISBN"]
        show_section(f"3) Ratings do ISBN {isbn_value}")
        results3 = [db.book_ratings.find_one({"ISBN": isbn_value})]
        show_results(results3, f"Ratings do livro {isbn_value}")
    else:
        print(" Não foi possível obter ISBN para a query 3.")

    client.close()
    print("\nFim do ScriptGoal2_MongoDB.\n")


if __name__ == "__main__":
    main()