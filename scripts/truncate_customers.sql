-- Run on Aurora **writer** before Gradescope resubmit if POST /customers returns 422 (userId already exists).
USE bookstore;
TRUNCATE TABLE customers;
