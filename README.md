<div align="center">

# 📚 BDA — Grupo 11

### Sistema híbrido de Bases de Dados **MySQL + MongoDB** sobre o dataset *Book-Crossing*

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-latest-47A248?logo=mongodb&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

**Dezembro de 2025**

</div>

---

## 👥 Autores

| Nome | Nº de aluno |
|------|:-----------:|
| Pedro Rosa | 60294 |
| Diogo Sousa | 60250 |
| Guilherme Almeida | 60264 |
| Francisco Lopes | 60252 |

> ✅ Todos os pontos do enunciado foram realizados neste projeto.

---

## 📖 Sobre o projeto

Este projeto, desenvolvido no âmbito da unidade curricular de **Bases de Dados Avançadas**, combina uma base de dados relacional (**MySQL**) com uma base de dados documental (**MongoDB**) para armazenar e consultar o dataset *Book-Crossing* — cerca de **270 mil livros**, **278 mil utilizadores** e **1,1 milhões de avaliações**.

O trabalho está dividido em quatro objetivos:

| Objetivo | Descrição | Script(s) |
|:--------:|-----------|-----------|
| **Goal 1** | Modelação e criação dos esquemas SQL e MongoDB e carregamento dos dados | `ScriptGoal1SQL.py`, `InsertDataSQL.py`, `create_schema.py`, `InsertDataMongoDB.py` |
| **Goal 2** | Queries SQL, MongoDB e híbridas (combinando as duas bases de dados) | `ScriptGoal2_Integrated.py` |
| **Goal 3** | Testes de concorrência e consistência (*lost update*, *dirty read*, *non-repeatable read*, *phantom read*, *serializable*, transações MongoDB) | `ScriptGoal3.py` |
| **Goal 4** | Otimização com índices, *benchmarks* e análise de planos de execução (`EXPLAIN`) | `ScriptGoal4.py`, `ExplainsGoal4.py` |

O relatório completo encontra-se em [`RelatórioBDA_Grupo11.pdf`](RelatórioBDA_Grupo11.pdf) e o diagrama ER em [`ER_Goal1.drawio`](ER_Goal1.drawio).

---

## 🗂️ Estrutura do repositório

```
BDA_Movies/
├── .env.example               # Modelo de configuração (copiar para .env)
├── .gitignore                 # Exclui o .env com as credenciais
├── config.py                  # Lê o .env e constrói a URI do MongoDB
├── docker-compose.yml         # Container do MongoDB local
│
├── books.csv                  # Dados: livros
├── users.csv                  # Dados: utilizadores
├── ratings.csv                # Dados: avaliações
│
├── ScriptGoal1SQL.py          # Goal 1 — cria a BD e tabelas MySQL
├── InsertDataSQL.py           # Goal 1 — popula o MySQL a partir dos CSV
├── create_schema.py           # Goal 1 — cria as coleções MongoDB (com validação $jsonSchema)
├── InsertDataMongoDB.py       # Goal 1 — popula o MongoDB a partir dos CSV
├── consistency_crossover.py   # Verificação de consistência entre MySQL e MongoDB
├── ScriptGoal2_Integrated.py  # Goal 2 — queries SQL, Mongo e híbridas
├── ScriptGoal3.py             # Goal 3 — testes de concorrência
├── ScriptGoal4.py             # Goal 4 — índices e benchmarks
├── ExplainsGoal4.py           # Goal 4 — planos de execução (EXPLAIN)
│
├── ER_Goal1.drawio            # Diagrama Entidade-Relação
└── RelatórioBDA_Grupo11.pdf   # Relatório final
```

---

## ⚙️ Pré-requisitos

- **Python 3.10+**
- **MySQL Server** (e, opcionalmente, **MySQL Workbench**)
- **MongoDB** — local via **Docker** ou na cloud via **MongoDB Atlas**

Instalar as dependências Python:

```bash
py -m pip install mysql-connector-python pymongo pandas python-dotenv
```

---

## 🔧 Configuração

Todas as ligações são configuradas no ficheiro **`.env`** na raiz do projeto. Este ficheiro **não está no repositório** (está no `.gitignore`), por isso é preciso criá-lo a partir do exemplo:

```bash
cp .env.example .env
```

Depois, preencher o `.env` com as credenciais reais:

```ini
# MySQL
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=<password>
MYSQL_DB=bda_Group11

# MongoDB Atlas (opcional — se definido, tem prioridade)
#MONGO_URI=mongodb+srv://<user>:<password>@<cluster>/

# MongoDB local
MONGO_DB=bda_Group11
MONGO_USER=root
MONGO_PASS=<password>
MONGO_HOST=localhost
MONGO_PORT=27017
DB_NAME=bda_Group11

LIMITED=True   # True = carrega só 20 000 linhas de cada CSV no MongoDB | False = dataset completo
N_RUNS=1       # Nº de execuções de cada query no benchmark do ScriptGoal4.py
```

> 💡 **MongoDB Atlas:** basta descomentar e preencher `MONGO_URI` — os restantes campos do MongoDB são ignorados.

---

## 🚀 Como executar

### 1. Arrancar o MongoDB local (Docker)

> Salta este passo se estiveres a usar o MongoDB Atlas.

O `docker-compose.yml` lê o utilizador e a password do MongoDB (`MONGO_USER` / `MONGO_PASS`) diretamente do `.env`, por isso este tem de estar criado antes.

```bash
docker pull mongo
docker-compose up -d
```

Para abrir uma shell no container (opcional):

```bash
docker exec -it mongodb mongosh -u root -p <password>
```

### 2. Garantir que o MySQL Server está a correr

Confirma que as credenciais do MySQL no `.env` estão corretas.

### 3. Executar os scripts pela seguinte ordem

| # | Comando | O que faz |
|:-:|---------|-----------|
| 1 | `python ScriptGoal1SQL.py` | Cria a base de dados `bda_Group11` e as tabelas MySQL |
| 2 | `python InsertDataSQL.py` | Popula as tabelas MySQL com os dados dos CSV |
| 3 | `python create_schema.py` | Cria as coleções MongoDB com validação de esquema |
| 4 | `python InsertDataMongoDB.py` | Popula o MongoDB e verifica a consistência com o MySQL |
| 5 | `python ScriptGoal2_Integrated.py` | Executa as queries SQL, MongoDB e híbridas |
| 6 | `python ScriptGoal3.py` | Executa os testes de concorrência em MySQL e MongoDB |
| 7 | `python ScriptGoal4.py` | Cria índices e compara tempos das queries antes/depois |
| 8 | `python ExplainsGoal4.py` | Mostra os planos de execução (`EXPLAIN`) das queries |

> ⏱️ **Tempos de referência** (MySQL local + MongoDB Atlas, `LIMITED=True`): o passo 2 demora ~5 min (insere sempre o dataset completo, ~1,15 M ratings) e o passo 4 ~7 min (no fim reconstrói `book_ratings` a partir do MySQL para garantir consistência). Os restantes passos demoram entre segundos e ~2 min. Com o MongoDB local (Docker) o passo 4 é mais rápido.

> ⚠️ Os passos **1 a 4** têm de ser executados antes dos restantes, por esta ordem. Os scripts `ScriptGoal1SQL.py` e `create_schema.py` **apagam** os dados existentes antes de recriar a estrutura.

> ℹ️ Algumas demonstrações de transações multi-documento no MongoDB (`ScriptGoal3.py`) requerem um *replica set* (por exemplo, MongoDB Atlas).

---

<div align="center">

Grupo 11 · Bases de Dados Avançadas · Dezembro de 2025

</div>
