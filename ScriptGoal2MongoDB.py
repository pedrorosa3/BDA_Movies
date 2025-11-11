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
    # 1) Livros com média de rating superior a X (ex: > 8) e mínimo N ratings (ex: >= 20)
    show_section("1) Livros com média de rating > 8 (>=20 ratings)")
    pipeline1 = [
        {"$unwind": "$ratings"},
        {"$group": {
            "_id": {"ISBN": "$ISBN", "book_title": "$book_title"},
            "avg_rating": {"$avg": "$ratings.book_rating"},
            "num_ratings": {"$sum": 1}
        }},
        {"$match": {"avg_rating": {"$gt": 8}, "num_ratings": {"$gte": 20}}},
        {"$sort": {"avg_rating": -1, "num_ratings": -1}},
        {"$limit": 10}
    ]
    results1 = list(db.books.aggregate(pipeline1))
    show_results(results1, "Top 10 (média > 8)")

    # 2) Procurar livros por autor OU título (regex case-insensitive)
    show_section("2) Pesquisa por autor/título (regex)")
    query2 = {
        "$or": [
            {"book_author": {"$regex": AUTHOR_DEMO, "$options": "i"}},
            {"book_title":  {"$regex": AUTHOR_DEMO, "$options": "i"}},
        ]
    }
    results2 = list(
        db.books.find(query2, {"ISBN": 1, "book_title": 1, "book_author": 1}).limit(10)
    )
    show_results(results2, f"Livros que combinam com '{AUTHOR_DEMO}'")

    # 3) Utilizadores com mais avaliações (contagem no campo embutido)
    show_section("3) Top utilizadores por nº de avaliações")
    pipeline3 = [
        {"$unwind": "$ratings"},
        {"$group": {"_id": "$ratings.user_id", "total_ratings": {"$sum": 1}}},
        {"$sort": {"total_ratings": -1}},
        {"$limit": 10}
    ]
    results3 = list(db.books.aggregate(pipeline3))
    show_results(results3, "Top 10 utilizadores com mais avaliações")

    # 4) Recomendações simples para USER_TARGET:
    #    - apanhar os ISBNs avaliados por USER_TARGET
    #    - apanhar outros livros avaliados por utilizadores que também avaliaram esses ISBNs
    #    - excluir livros já avaliados pelo USER_TARGET
    #    - ordenar por média
    show_section(f"4) Recomendações simples (user-based lite) para user {USER_TARGET}")
    # 4.1 ISBNs avaliados pelo user
    user_books_cursor = db.books.find({"ratings.user_id": USER_TARGET}, {"ISBN": 1})
    user_isbns = [doc["ISBN"] for doc in user_books_cursor]
    if user_isbns:
        pipeline4 = [
            {"$match": {"ISBN": {"$in": user_isbns}}},
            {"$unwind": "$ratings"},
            {"$match": {"ratings.user_id": {"$ne": USER_TARGET}}},  # outros users
            # Agora queremos os OUTROS livros que esses users avaliaram:
            # Reunimos todos os user_ids relevantes e, depois, buscamos os livros
        ]
        other_users = list(
            db.books.aggregate(pipeline4 + [
                {"$group": {"_id": "$ratings.user_id"}},
                {"$project": {"_id": 0, "user_id": "$_id"}}
            ])
        )
        other_user_ids = [u["user_id"] for u in other_users]

        if other_user_ids:
            pipeline4b = [
                {"$unwind": "$ratings"},
                {"$match": {
                    "ratings.user_id": {"$in": other_user_ids},
                    "ISBN": {"$nin": user_isbns}  # excluir o que o user já avaliou
                }},
                {"$group": {
                    "_id": {"ISBN": "$ISBN", "title": "$book_title"},
                    "avg_rating": {"$avg": "$ratings.book_rating"},
                    "num_ratings": {"$sum": 1}
                }},
                {"$match": {"num_ratings": {"$gte": 5}}},
                {"$sort": {"avg_rating": -1, "num_ratings": -1}},
                {"$limit": 10}
            ]
            results4 = list(db.books.aggregate(pipeline4b))
        else:
            results4 = []
    else:
        results4 = []
    show_results(results4, "Sugestões (outros livros avaliados por utilizadores parecidos)")

    # 5) Integração simples com MySQL: receber IDs de utilizadores ativos (lista)
    #    e mostrar informações deles (age, location) no Mongo
    show_section("5) Detalhes de utilizadores ativos (vindos do MySQL)")
    results5 = list(
        db.users.find(
            {"user_id": {"$in": ACTIVE_USERS_FROM_SQL}},
            {"_id": 0, "user_id": 1, "age": 1, "location": 1}
        )
    )
    show_results(results5, f"Detalhes dos utilizadores {ACTIVE_USERS_FROM_SQL}")

    # 6) Content-based: livros semelhantes ao ISBN_TARGET (mesmo autor OU mesma editora)
    show_section(f"6) Content-based: semelhantes ao ISBN {ISBN_TARGET}")
    target = db.books.find_one({"ISBN": ISBN_TARGET}, {"book_author": 1, "publisher": 1})
    if target:
        query6 = {
            "$or": [
                {"book_author": target.get("book_author")},
                {"publisher":   target.get("publisher")}
            ],
            "ISBN": {"$ne": ISBN_TARGET}
        }
        results6 = list(
            db.books.find(query6, {"ISBN": 1, "book_title": 1, "book_author": 1, "publisher": 1}).limit(10)
        )
    else:
        results6 = []
    show_results(results6, "Livros semelhantes (mesmo autor/editora)")

    # 7) Preferências contextuais: autor + ano mínimo (filtros flexíveis)
    show_section("7) Preferências contextuais (autor + ano mínimo)")
    query7 = {
        "book_author": {"$regex": AUTHOR_DEMO, "$options": "i"},
        "year_of_publication": {"$gte": YEAR_MIN}
    }
    results7 = list(
        db.books.find(query7, {"ISBN": 1, "book_title": 1, "book_author": 1, "year_of_publication": 1}).limit(10)
    )
    show_results(results7, f"Livros de '{AUTHOR_DEMO}' após {YEAR_MIN}")

    # 8) Autores mais apreciados 
    show_section("8) Autores mais apreciados (média de ratings)")
    pipeline8 = [
        {"$unwind": "$ratings"},
        {"$group": {
            "_id": "$book_author",
            "avg_rating": {"$avg": "$ratings.book_rating"},
            "num_ratings": {"$sum": 1}
        }},
        {"$match": {"num_ratings": {"$gte": 20}}},
        {"$sort": {"avg_rating": -1}},
        {"$limit": 10}
    ]
    results8 = list(db.books.aggregate(pipeline8))
    show_results(results8, "Top autores (média + volume)")

    # 9) Livros populares por localização
    #    - Fazemos lookup de users pelos user_id existentes nas ratings
    #    - Agregamos por location e listamos top títulos
    show_section("9) Livros populares por localização (lookup users)")
    pipeline9 = [
        {"$unwind": "$ratings"},
        {"$lookup": {
            "from": "users",
            "localField": "ratings.user_id",
            "foreignField": "user_id",
            "as": "user_info"
        }},
        {"$unwind": "$user_info"},
        {"$group": {
            "_id": {"location": "$user_info.location", "title": "$book_title"},
            "num_ratings": {"$sum": 1},
            "avg_rating": {"$avg": "$ratings.book_rating"}
        }},
        {"$match": {"_id.location": {"$ne": None}}},
        {"$sort": {"num_ratings": -1, "avg_rating": -1}},
        # Opcional: poderias re-agrupar por location e fazer top-N por região
        {"$limit": 25}
    ]
    results9 = list(db.books.aggregate(pipeline9))
    show_results(results9, "Títulos populares agrupados por localização")

    # 10) Híbrida: livros favoritos dos utilizadores mais ativos (IDs vindos do SQL)
    show_section("10) Híbrida (MySQL -> Mongo): favoritos dos utilizadores ativos")
    pipeline10 = [
        {"$unwind": "$ratings"},
        {"$match": {"ratings.user_id": {"$in": ACTIVE_USERS_FROM_SQL}}},
        {"$group": {
            "_id": {"ISBN": "$ISBN", "title": "$book_title"},
            "avg_rating": {"$avg": "$ratings.book_rating"},
            "num_ratings": {"$sum": 1}
        }},
        {"$match": {"num_ratings": {"$gte": 5}}},
        {"$sort": {"avg_rating": -1, "num_ratings": -1}},
        {"$limit": 10}
    ]
    results10 = list(db.books.aggregate(pipeline10))
    show_results(results10, "Top livros entre os utilizadores ativos")

    client.close()
    print("\n Fim do ScriptGoal2_MongoDB.\n")

if __name__ == "__main__":
    main()
