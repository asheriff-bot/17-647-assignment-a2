-- Run this once against Aurora MySQL (writer endpoint) after stack creation.
-- mysql -h <cluster-endpoint> -u <DBUsername> -p < init_db.sql

CREATE DATABASE IF NOT EXISTS bookstore;
USE bookstore;

CREATE TABLE IF NOT EXISTS customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  userId VARCHAR(64) NOT NULL,
  name VARCHAR(255),
  address VARCHAR(255),
  address2 VARCHAR(255),
  city VARCHAR(100),
  state VARCHAR(50),
  zipcode VARCHAR(20),
  INDEX idx_userId (userId)
);

CREATE TABLE IF NOT EXISTS books (
  isbn VARCHAR(32) PRIMARY KEY,
  title VARCHAR(255),
  author VARCHAR(255),
  genre VARCHAR(64)
);

INSERT INTO books (isbn, title, author, genre) VALUES
  ('978-0-13-235088-4', 'Clean Code', 'Robert Martin', 'non-fiction'),
  ('978-0-321-53410-4', 'The Pragmatic Programmer', 'Hunt and Thomas', 'non-fiction'),
  ('978-0-13-468599-1', 'Effective Java', 'Joshua Bloch', 'non-fiction')
ON DUPLICATE KEY UPDATE title=VALUES(title);
