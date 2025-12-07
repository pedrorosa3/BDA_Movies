# ============================================================
#  ExplainMongo.py
#  Comparação Goal 2 vs Goal 4 para MongoDB (Query 4 e 5)
# ============================================================

from pymongo import MongoClient
from config import Config
import pprint
import sys


# ============================================================
#  LIGAÇÃO
# ============================================================
def get_mongo_client():
    try:
        return MongoClient(Config.build_mongo_uri())
    except Exception as e:
        print("Erro ao ligar ao MongoDB:", e, file=sys.stderr)
        raise


# ============================================================
#  REMOVER ÍNDICES (para simular GOAL 2)
# ============================================================
def drop_all_mongo_indexes():
    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    print("\n[MongoDB] A remover TODOS os índices (exceto _id_)...\n")

    for coll_name in db.list_collection_names():
        coll = db[coll_name]
        print(f"  > Coleção: {coll_name}")
        for idx in coll.list_indexes():
            name = idx["name"]
            if name == "_id_":
                continue
            print(f"     - dropIndex({name})")
            coll.drop_index(name)

    client.close()


# ============================================================
#  CRIAR ÍNDICES DO GOAL 4
# ============================================================
def create_mongo_indexes():
    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    print("\n[MongoDB] A criar índices OTIMIZADOS (Goal 4)...\n")

    db.book_ratings.create_index([("ISBN", 1)], name="idx_book_ratings_isbn")
    db.book_ratings.create_index([("ratings.user_id", 1)], name="idx_book_ratings_ratings_user_id")
    db.book_ratings.create_index([("ISBN", 1), ("ratings.user_id", 1)], name="idx_book_ratings_isbn_user_composto")

    db.users.create_index([("location", 1)], name="idx_users_location")
    db.users.create_index([("location", 1), ("user_id", 1)], name="idx_users_location_user_composto")

    client.close()


# ============================================================
#  PIPELINES ORIGINAIS (GOAL 2)
# ============================================================

pipeline_top_users = [
    {"$unwind": "$ratings"},
    {"$group": {"_id": "$ratings.user_id", "total": {"$sum": 1}}},
    {"$sort": {"total": -1}},
    {"$limit": 10},
    {"$project": {"user_id": "$_id", "total": 1, "_id": 0}},
]

pipeline_top_localizacoes = [
    {"$match": {"location": {"$ne": None}}},
    {"$group": {"_id": "$location", "num_users": {"$sum": 1}}},
    {"$sort": {"num_users": -1}},
    {"$limit": 10},
    {"$project": {"location": "$_id", "num_users": 1, "_id": 0}},
]


# ============================================================
#  PRETTY EXPLAIN FORMATTER (Mongo)
# ============================================================
def explain_mongo(collection, pipeline, label):
    client = get_mongo_client()
    db = client[Config.MONGO_DB]

    print("\n" + "=" * 110)
    print(label)
    print("=" * 110)

    try:
        cmd = {
            "explain": {
                "aggregate": collection,
                "pipeline": pipeline,
                "cursor": {}
            },
            "verbosity": "executionStats"
        }

        result = db.command(cmd)

        # -----------------------------
        # EXTRAÇÃO SEGURA (compatível MongoDB 5-8)
        # -----------------------------
        try:
            cursor_stage = result["stages"][0]["$cursor"]["executionStats"]

            exec_stage = cursor_stage["executionStages"]
            winning_stage = exec_stage["inputStage"].get("stage", "N/A")

            index_name = exec_stage["inputStage"].get("indexName", "N/A")

            docs_examined = cursor_stage.get("totalDocsExamined", "N/A")
            docs_returned = cursor_stage.get("nReturned", "N/A")
            exec_time = cursor_stage.get("executionTimeMillis", "N/A")

        except Exception:
            # fallback genérico caso outra versão do Mongo apareça
            winning_stage = "N/A"
            index_name = "N/A"
            docs_examined = "N/A"
            docs_returned = "N/A"
            exec_time = "N/A"

        # -----------------------------
        # PRINT SIMPLIFICADO
        # -----------------------------
        print(f"Winning Stage:            {winning_stage}")
        print(f"Index Used:               {index_name}")
        print(f"Documents Examined:       {docs_examined}")
        print(f"Documents Returned:       {docs_returned}")
        print(f"Execution Time (ms):      {exec_time}")

    finally:
        client.close()




# ============================================================
#  MAIN — EXPLAIN ANTES / DEPOIS
# ============================================================
def main():

    # 1) Remover índices → GOAL 2
    drop_all_mongo_indexes()

    print("\n====================== GOAL 2 (ORIGINAL) — EXPLAIN ======================")

    explain_mongo(
        collection="book_ratings",
        pipeline=pipeline_top_users,
        label="GOAL 2 — Query 4 (Original) — Top Users"
    )

    explain_mongo(
        collection="users",
        pipeline=pipeline_top_localizacoes,
        label="GOAL 2 — Query 5 (Original) — Top Localizações"
    )

    # 2) Criar índices → GOAL 4
    create_mongo_indexes()

    print("\n====================== GOAL 4 (OTIMIZADO) — EXPLAIN ======================")

    explain_mongo(
        collection="book_ratings",
        pipeline=pipeline_top_users,
        label="GOAL 4 — Query 4 (Otimizada) — Top Users"
    )

    explain_mongo(
        collection="users",
        pipeline=pipeline_top_localizacoes,
        label="GOAL 4 — Query 5 (Otimizada) — Top Localizações"
    )


if __name__ == "__main__":
    main()
