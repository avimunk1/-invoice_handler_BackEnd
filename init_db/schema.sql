-- MVP Database Schema – Accounting System
-- This file is mounted into the container at /docker-entrypoint-initdb.d/schema.sql
-- You can apply it manually or let Docker initialize it on first run.

------------------------------------------------------------
-- CUSTOMERS (Accounting clients)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
  id               SERIAL PRIMARY KEY,
  name             VARCHAR(200) NOT NULL,
  tax_code         VARCHAR(30),
  is_self_employed BOOLEAN NOT NULL DEFAULT FALSE,
  active           BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMP,
  deleted_at       TIMESTAMP,
  deleted_by       INT
);

CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);

------------------------------------------------------------
-- USERS
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id              SERIAL PRIMARY KEY,
  email           VARCHAR(255) UNIQUE NOT NULL,
  full_name       VARCHAR(200),
  role            VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'accountant', 'customer')),
  customer_id     INT,
  password_hash   TEXT,
  active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMP
);

-- Add FK after both tables exist
ALTER TABLE users
  ADD CONSTRAINT users_customer_fk
  FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_customer ON users(customer_id);

------------------------------------------------------------
-- EXPENSE ACCOUNTS (System-wide catalog)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS expense_accounts (
  id                     SERIAL PRIMARY KEY,
  code                   VARCHAR(20) UNIQUE NOT NULL,
  name                   VARCHAR(200) NOT NULL,
  description            TEXT,
  default_deductible_pct NUMERIC(5,2) NOT NULL DEFAULT 100.00,
  active                 BOOLEAN NOT NULL DEFAULT TRUE
);

------------------------------------------------------------
-- SUPPLIERS (Per customer)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suppliers (
  id                          SERIAL PRIMARY KEY,
  customer_id                 INT NOT NULL,
  name                        VARCHAR(200) NOT NULL,
  ocr_supplier_identification VARCHAR(255),
  currency                    VARCHAR(3),
  default_expense_account_id  INT,
  default_deductible_pct      NUMERIC(5,2),
  active                      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at                  TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at                  TIMESTAMP,
  updated_by                  INT,
  deleted_at                  TIMESTAMP,
  deleted_by                  INT,
  UNIQUE (customer_id, name),
  UNIQUE (customer_id, ocr_supplier_identification)
);

ALTER TABLE suppliers
  ADD CONSTRAINT suppliers_customer_fk
  FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT;

ALTER TABLE suppliers
  ADD CONSTRAINT suppliers_expense_account_fk
  FOREIGN KEY (default_expense_account_id) REFERENCES expense_accounts(id);

ALTER TABLE suppliers
  ADD CONSTRAINT suppliers_updated_by_fk
  FOREIGN KEY (updated_by) REFERENCES users(id);

CREATE INDEX IF NOT EXISTS idx_suppliers_customer ON suppliers(customer_id);
CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);

------------------------------------------------------------
-- INVOICES (Single-line model for MVP)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices (
  id                 SERIAL PRIMARY KEY,
  customer_id        INT NOT NULL,
  supplier_id        INT NOT NULL,
  invoice_number     VARCHAR(80) NOT NULL,
  invoice_date       DATE NOT NULL,
  due_date           DATE,
  currency           VARCHAR(3) NOT NULL,
  subtotal           NUMERIC(14,2) NOT NULL,
  vat_amount         NUMERIC(14,2) NOT NULL DEFAULT 0.00,
  total              NUMERIC(14,2) NOT NULL,
  expense_account_id INT,
  deductible_pct     NUMERIC(5,2),
  doc_name           VARCHAR(255),
  doc_full_path      TEXT,
  document_type      VARCHAR(20) DEFAULT 'invoice' CHECK (document_type IN ('invoice', 'receipt', 'other')),
  status             VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'exported', 'rejected')),
  ocr_confidence     NUMERIC(3,2),
  ocr_language       VARCHAR(5),
  ocr_metadata       JSONB,
  needs_review       BOOLEAN DEFAULT FALSE,
  duplicate_of       INT,
  payment_terms      VARCHAR(50),
  created_by         INT,
  created_at         TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMP,
  updated_by         INT,
  deleted_at         TIMESTAMP,
  deleted_by         INT,
  UNIQUE (customer_id, supplier_id, invoice_number)
);

ALTER TABLE invoices
  ADD CONSTRAINT invoices_customer_fk
  FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT;

ALTER TABLE invoices
  ADD CONSTRAINT invoices_supplier_fk
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT;

ALTER TABLE invoices
  ADD CONSTRAINT invoices_expense_account_fk
  FOREIGN KEY (expense_account_id) REFERENCES expense_accounts(id);

ALTER TABLE invoices
  ADD CONSTRAINT invoices_duplicate_fk
  FOREIGN KEY (duplicate_of) REFERENCES invoices(id);

ALTER TABLE invoices
  ADD CONSTRAINT invoices_created_by_fk
  FOREIGN KEY (created_by) REFERENCES users(id);

ALTER TABLE invoices
  ADD CONSTRAINT invoices_updated_by_fk
  FOREIGN KEY (updated_by) REFERENCES users(id);

CREATE INDEX IF NOT EXISTS idx_invoices_customer_date ON invoices(customer_id, invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_needs_review ON invoices(needs_review) WHERE needs_review = TRUE;


