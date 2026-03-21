-- A1 schema + sample rows (run against Aurora writer).
CREATE DATABASE IF NOT EXISTS bookstore;
USE bookstore;

DROP TABLE IF EXISTS books;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  userId VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  phone VARCHAR(64) NOT NULL,
  address VARCHAR(255) NOT NULL,
  address2 VARCHAR(255) NULL,
  city VARCHAR(100) NOT NULL,
  state VARCHAR(2) NOT NULL,
  zipcode VARCHAR(20) NOT NULL,
  UNIQUE KEY uq_userId (userId)
);

CREATE TABLE books (
  isbn VARCHAR(32) PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  author VARCHAR(255) NOT NULL,
  description TEXT NOT NULL,
  genre VARCHAR(64) NOT NULL,
  price DECIMAL(12, 2) NOT NULL,
  quantity INT NOT NULL,
  summary TEXT NULL
);

INSERT INTO books (isbn, title, author, description, genre, price, quantity, summary) VALUES
  ('978-0-13-235088-4', 'Clean Code', 'Robert Martin', 'A handbook of agile software craftsmanship.', 'non-fiction', 42.00, 10, 'Summary placeholder for Clean Code.'),
  ('978-0-321-53410-4', 'The Pragmatic Programmer', 'Hunt and Thomas', 'Tips for pragmatic developers.', 'non-fiction', 49.99, 5, 'Summary placeholder for Pragmatic Programmer.'),
  ('978-0-13-468599-1', 'Effective Java', 'Joshua Bloch', 'Best practices for Java.', 'non-fiction', 54.50, 8, 'Summary placeholder for Effective Java.')
ON DUPLICATE KEY UPDATE title=VALUES(title);
