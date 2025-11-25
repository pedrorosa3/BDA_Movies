-- PONTO 1 - Indices para melhorar performance das queries
-- Índice obrigatório para aceleração das vossas queries
ALTER TABLE ratings
  ADD INDEX idx_ratings_isbn (ISBN);

-- Acedem muito a user_id durante concorrência → criar índice
ALTER TABLE ratings
  ADD INDEX idx_ratings_user (user_id);

-- Índice composto ajuda quer leitores, quer escritores
ALTER TABLE ratings
  ADD INDEX idx_ratings_isbn_user (ISBN, user_id);

-- Se fazem busca por título
ALTER TABLE books
  ADD INDEX idx_books_title (book_title(100));



-- PONTO 2 - Reduzir joins repetidos


CREATE TABLE IF NOT EXISTS book_stats AS
SELECT ISBN,
       COUNT(*) AS total_ratings,
       AVG(book_rating) AS avg_rating
FROM ratings
GROUP BY ISBN;

ALTER TABLE book_stats ADD INDEX idx_stats_total (total_ratings);

--
--Query passa a ser assim:

--SELECT b.book_title, s.total_ratings
--FROM book_stats s
--JOIN books b ON b.ISBN = s.ISBN
--ORDER BY s.total_ratings DESC
--LIMIT 10;

