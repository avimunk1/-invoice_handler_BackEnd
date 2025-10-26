
# 📘 MVP Database Schema – Accounting System

This schema supports a **single accounting firm** managing multiple **customers** (self-employed or companies).  
Each customer manages their **suppliers** and **invoices**, linked to a shared set of **expense accounts**.

---

## 👤 Users

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| email | VARCHAR(255) | Unique email (login ID) |
| full_name | VARCHAR(200) | User full name |
| role | VARCHAR(20) | One of `admin`, `accountant`, `customer` |
| customer_id | INT | References `customers(id)` - Set only for `role='customer'` |
| password_hash | TEXT | Optional, if not using SSO |
| active | BOOLEAN | Default `TRUE` |
| created_at | TIMESTAMP | Default `NOW()` |
| updated_at | TIMESTAMP | Last update timestamp |

**Indexes:**  
`idx_users_role`, `idx_users_customer`

---

## 🧾 Customers

Represents a client of the accounting firm.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| name | VARCHAR(200) | Customer or business name |
| tax_code | VARCHAR(30) | Customer VAT or tax ID |
| is_self_employed | BOOLEAN | Default `FALSE` |
| active | BOOLEAN | Default `TRUE` |
| created_at | TIMESTAMP | Default `NOW()` |
| updated_at | TIMESTAMP | Last update timestamp |
| deleted_at | TIMESTAMP | Soft delete timestamp |
| deleted_by | INT | References `users(id)` |

**Index:** `idx_customers_name`

---

## 💼 Expense Accounts

Global catalog of expense types (e.g., Rent, Travel, Services, etc.)

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| code | VARCHAR(20) | Unique expense code |
| name | VARCHAR(200) | Expense category name |
| description | TEXT | Optional |
| default_deductible_pct | NUMERIC(5,2) | Default `100.00` |
| active | BOOLEAN | Default `TRUE` |

---

## 🧑‍💻 Suppliers

Each customer has their own supplier list.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| customer_id | INT | References `customers(id)` |
| name | VARCHAR(200) | Normalized supplier name |
| ocr_supplier_identification | VARCHAR(255) | Supplier name as received from OCR |
| currency | VARCHAR(3) | Default supplier currency |
| default_expense_account_id | INT | References `expense_accounts(id)` |
| default_deductible_pct | NUMERIC(5,2) | Optional override |
| active | BOOLEAN | Default `TRUE` |
| created_at | TIMESTAMP | Default `NOW()` |
| updated_at | TIMESTAMP | Last update timestamp |
| updated_by | INT | References `users(id)` |
| deleted_at | TIMESTAMP | Soft delete timestamp |
| deleted_by | INT | References `users(id)` |

**Unique constraints:**  
- `(customer_id, name)`  
- `(customer_id, ocr_supplier_identification)`

**Indexes:**  
`idx_suppliers_customer`, `idx_suppliers_name`

---

## 📄 Invoices

Each invoice represents one expense record (single-line MVP).

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| customer_id | INT | References `customers(id)` |
| supplier_id | INT | References `suppliers(id)` |
| invoice_number | VARCHAR(80) | Supplier invoice number |
| invoice_date | DATE | Invoice date |
| due_date | DATE | Payment due date (optional) |
| currency | VARCHAR(3) | Invoice currency |
| subtotal | NUMERIC(14,2) | Amount before VAT |
| vat_amount | NUMERIC(14,2) | VAT amount (no VAT code stored) |
| total | NUMERIC(14,2) | Subtotal + VAT |
| expense_account_id | INT | Optional override of supplier default |
| deductible_pct | NUMERIC(5,2) | Optional override |
| doc_name | VARCHAR(255) | File name of the document |
| doc_full_path | TEXT | Full path or storage URI |
| document_type | VARCHAR(20) | One of `invoice`, `receipt`, `other` |
| status | VARCHAR(20) | One of `pending`, `approved`, `exported`, `rejected` |
| ocr_confidence | NUMERIC(3,2) | Overall OCR confidence (0.00 to 1.00) |
| ocr_language | VARCHAR(5) | Detected language (e.g., `en`, `he`) |
| ocr_metadata | JSONB | Bounding boxes, field confidence, page count, etc. |
| needs_review | BOOLEAN | Flag for low-confidence invoices requiring manual review |
| duplicate_of | INT | References `invoices(id)` - Link to potential duplicate |
| payment_terms | VARCHAR(50) | Payment terms description (optional) |
| created_by | INT | References `users(id)` |
| created_at | TIMESTAMP | Default `NOW()` |
| updated_at | TIMESTAMP | Last update timestamp |
| updated_by | INT | References `users(id)` |
| deleted_at | TIMESTAMP | Soft delete timestamp |
| deleted_by | INT | References `users(id)` |

**Unique constraint:** `(customer_id, supplier_id, invoice_number)`

**Indexes:**  
`idx_invoices_customer_date`, `idx_invoices_supplier`, `idx_invoices_status`, `idx_invoices_needs_review`

---

## 🔗 Entity Relationships

| Entity | Description | Relationships |
|--------|--------------|----------------|
| **users** | Application users | Optionally linked to one customer |
| **customers** | Accounting firm clients | Own suppliers & invoices |
| **expense_accounts** | Global expense categories | Referenced by suppliers & invoices |
| **suppliers** | Vendors per customer | Link to one expense account |
| **invoices** | Expense records | Link to customer, supplier, and expense account |

---

## 🔐 Access Control

| Role | Access |
|------|--------|
| **admin** | Full access to all data |
| **accountant** | Access to all customers, suppliers, invoices |
| **customer** | Access restricted to their own `customer_id` |

---

## 🔄 Typical Flow

**1️⃣ Customer upload (self-employed/company):**
- OCR extracts supplier name → stored in `ocr_supplier_identification`.
- System auto-matches or creates supplier.
- Expense account & deductible % pulled from supplier defaults.

**2️⃣ Accountant review/export:**
- Accountant filters by customer.
- Reviews or edits expense account/deductible %.
- Export to accounting software — VAT code and entries resolved from config.

---

## 💾 SQL DDL

------------------------------------------------------------
-- USERS
------------------------------------------------------------
CREATE TABLE users (
  id              SERIAL PRIMARY KEY,
  email           VARCHAR(255) UNIQUE NOT NULL,
  full_name       VARCHAR(200),
  role            VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'accountant', 'customer')),
  customer_id     INT REFERENCES customers(id) ON DELETE SET NULL,  -- linked only for role='customer'
  password_hash   TEXT,                                              -- optional if using SSO
  active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMP
);

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_customer ON users(customer_id);

------------------------------------------------------------
-- CUSTOMERS (Accounting clients)
------------------------------------------------------------
CREATE TABLE customers (
  id               SERIAL PRIMARY KEY,
  name             VARCHAR(200) NOT NULL,
  tax_code         VARCHAR(30),                         -- customer VAT/Tax identifier
  is_self_employed BOOLEAN NOT NULL DEFAULT FALSE,
  active           BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMP,
  deleted_at       TIMESTAMP,
  deleted_by       INT REFERENCES users(id)
);

CREATE INDEX idx_customers_name ON customers(name);

------------------------------------------------------------
-- EXPENSE ACCOUNTS (System-wide catalog)
------------------------------------------------------------
CREATE TABLE expense_accounts (
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
CREATE TABLE suppliers (
  id                         SERIAL PRIMARY KEY,
  customer_id                INT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
  name                       VARCHAR(200) NOT NULL,          -- normalized supplier name
  ocr_supplier_identification VARCHAR(255),                  -- name as received from OCR
  currency                   VARCHAR(3),
  default_expense_account_id INT REFERENCES expense_accounts(id),
  default_deductible_pct     NUMERIC(5,2),
  active                     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at                 TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at                 TIMESTAMP,
  updated_by                 INT REFERENCES users(id),
  deleted_at                 TIMESTAMP,
  deleted_by                 INT REFERENCES users(id),
  UNIQUE (customer_id, name),
  UNIQUE (customer_id, ocr_supplier_identification)
);

CREATE INDEX idx_suppliers_customer ON suppliers(customer_id);
CREATE INDEX idx_suppliers_name ON suppliers(name);

------------------------------------------------------------
-- INVOICES (Single-line model for MVP)
------------------------------------------------------------
CREATE TABLE invoices (
  id                 SERIAL PRIMARY KEY,
  customer_id        INT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
  supplier_id        INT NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
  invoice_number     VARCHAR(80) NOT NULL,
  invoice_date       DATE NOT NULL,
  due_date           DATE,
  currency           VARCHAR(3) NOT NULL,
  subtotal           NUMERIC(14,2) NOT NULL,              -- net amount before VAT
  vat_amount         NUMERIC(14,2) NOT NULL DEFAULT 0.00, -- only the VAT amount (no VAT code)
  total              NUMERIC(14,2) NOT NULL,              -- subtotal + vat_amount
  expense_account_id INT REFERENCES expense_accounts(id), -- override of supplier default
  deductible_pct     NUMERIC(5,2),                        -- override of default
  doc_name           VARCHAR(255),
  doc_full_path      TEXT,
  document_type      VARCHAR(20) DEFAULT 'invoice' CHECK (document_type IN ('invoice', 'receipt', 'other')),
  status             VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'exported', 'rejected')),
  ocr_confidence     NUMERIC(3,2),                        -- 0.00 to 1.00
  ocr_language       VARCHAR(5),                          -- 'en', 'he', etc.
  ocr_metadata       JSONB,                               -- bounding boxes, field confidence, page count
  needs_review       BOOLEAN DEFAULT FALSE,               -- flag for low-confidence invoices
  duplicate_of       INT REFERENCES invoices(id),         -- link to potential duplicate
  payment_terms      VARCHAR(50),
  created_by         INT REFERENCES users(id),
  created_at         TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMP,
  updated_by         INT REFERENCES users(id),
  deleted_at         TIMESTAMP,
  deleted_by         INT REFERENCES users(id),
  UNIQUE (customer_id, supplier_id, invoice_number)
);

CREATE INDEX idx_invoices_customer_date ON invoices(customer_id, invoice_date);
CREATE INDEX idx_invoices_supplier ON invoices(supplier_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_needs_review ON invoices(needs_review) WHERE needs_review = TRUE;

---

**Notes for Developers**

* The MVP assumes one accounting firm (no multi-tenant isolation yet).
* All VAT logic and accounting export mapping are handled **outside** the DB (in configuration).
* You can extend to multiple lines per invoice or multiple OCR aliases later.
* Add RLS or app-level filters by `customer_id` for data isolation.
* Soft deletes (`deleted_at`, `deleted_by`) provide audit trails instead of hard deletes.
* `ocr_metadata` JSONB field stores bounding boxes, field confidence, and page count from OCR processing.
* `needs_review` flag automatically set when `ocr_confidence < 0.70` to prioritize manual review.
* Foreign key constraints use `RESTRICT` to prevent accidental data loss.

**OCR Integration Fields**

The schema integrates seamlessly with the invoice handler OCR pipeline:
* `document_type` matches OCR detection (`invoice`, `receipt`, `other`)
* `ocr_confidence` stores overall confidence score
* `ocr_language` stores detected language (e.g., `he`, `en`)
* `ocr_metadata` example structure:
  ```json
  {
    "bounding_boxes": {
      "supplier_name": {"page_number": 1, "polygon": [[x1, y1], [x2, y2], ...]},
      "total": {"page_number": 1, "polygon": [[x1, y1], [x2, y2], ...]}
    },
    "field_confidence": {
      "supplier_name": 0.95,
      "invoice_number": 0.48,
      "total": 0.87
    },
    "page_count": 2
  }
  ```

