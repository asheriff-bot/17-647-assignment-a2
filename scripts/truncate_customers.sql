-- Run on Aurora writer before re-testing or resubmitting Gradescope if POST /customers keeps returning 422.
USE bookstore;
TRUNCATE TABLE customers;
