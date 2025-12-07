# BDA_Group11
Diogo Sousa nº60250
Francisco Lopes nº60252
Guilherme Almeida nº60264
Pedro Rosa nº60294

- É de frisar que todos os pontos do enunciado foram realizados neste projeto.

## MongoDB Atlas
Pré‑requisitos:
```bash
py -m pip install mysql-connector-python pymongo pandas dotenv
```
Caso a ligação seja feita via Atlas basta alterar o URI no ficheiro .env

## MongoDB Local
Pré‑requisitos:
```bash
py -m pip install mysql-connector-python pymongo pandas dotenv
```

Criar container do MongoDB:
```bash
docker pull mongo
docker-compose up -d
docker exec -it mongodb mongosh -u root -p <password>
```
Criar schema:
```bash
python create_schema.py
```
Popular a base de dados:
- Executar `InsertDataMongoDB.py`

## MySQL Local
Instalar:
- MySQL Server  
- MySQL Workbench


Executar scripts na seguinte ordem:
1. `ScriptGoal1SQL.py` – cria a base de dados e tabelas SQl.
2. `InsertDataSQL.py` – popula as tabelas SQL com os CSV.
1. `create_schema.py` – cria a base de dados e tabelas Mongo.
1. `InsertDataMongo.py` – popula as tabelas Mongo com os CSV.
2. `ScriptGoal2_Integrated.py` – Faz as queries para SQL e Mongo.
3. `ScriptGoal3.py` – Faz testes de concorrência em SQL e em Mongo.
3. `ScriptGoal4.py` – Otimiza as bases de dados e as querys através de indexs.