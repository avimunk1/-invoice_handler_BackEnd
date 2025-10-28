"""SQLAlchemy Core table definitions."""
from sqlalchemy import (
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Boolean,
    Numeric,
    Date,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

customers = Table(
    "customers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(200), nullable=False),
    Column("tax_code", String(30)),
    Column("is_self_employed", Boolean, nullable=False, server_default="false"),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime),
    Column("deleted_at", DateTime),
    Column("deleted_by", Integer),
)

Index("idx_customers_name", customers.c.name)

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String(255), unique=True, nullable=False),
    Column("full_name", String(200)),
    Column("role", String(20), nullable=False),
    Column("customer_id", Integer, ForeignKey("customers.id", ondelete="SET NULL")),
    Column("password_hash", Text),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime),
    CheckConstraint("role IN ('admin', 'accountant', 'customer')", name="users_role_check"),
)

Index("idx_users_role", users.c.role)
Index("idx_users_customer", users.c.customer_id)

expense_accounts = Table(
    "expense_accounts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("code", String(20), unique=True, nullable=False),
    Column("name", String(200), nullable=False),
    Column("description", Text),
    Column("default_deductible_pct", Numeric(5, 2), nullable=False, server_default="100.00"),
    Column("active", Boolean, nullable=False, server_default="true"),
)

suppliers = Table(
    "suppliers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("customer_id", Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("ocr_supplier_identification", String(255)),
    Column("currency", String(3)),
    Column("default_expense_account_id", Integer, ForeignKey("expense_accounts.id")),
    Column("default_deductible_pct", Numeric(5, 2)),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime),
    Column("updated_by", Integer, ForeignKey("users.id")),
    Column("deleted_at", DateTime),
    Column("deleted_by", Integer),
    UniqueConstraint("customer_id", "name", name="suppliers_customer_id_name_key"),
    UniqueConstraint("customer_id", "ocr_supplier_identification", name="suppliers_customer_id_ocr_key"),
)

Index("idx_suppliers_customer", suppliers.c.customer_id)
Index("idx_suppliers_name", suppliers.c.name)

invoices = Table(
    "invoices",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("customer_id", Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
    Column("supplier_id", Integer, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
    Column("invoice_number", String(80), nullable=False),
    Column("invoice_date", Date, nullable=False),
    Column("due_date", Date),
    Column("currency", String(3), nullable=False),
    Column("subtotal", Numeric(14, 2), nullable=False),
    Column("vat_amount", Numeric(14, 2), nullable=False, server_default="0.00"),
    Column("total", Numeric(14, 2), nullable=False),
    Column("expense_account_id", Integer, ForeignKey("expense_accounts.id")),
    Column("deductible_pct", Numeric(5, 2)),
    Column("doc_name", String(255)),
    Column("doc_full_path", Text),
    Column("document_type", String(20), server_default="invoice"),
    Column("status", String(20), server_default="pending"),
    Column("ocr_confidence", Numeric(3, 2)),
    Column("ocr_language", String(5)),
    Column("ocr_metadata", JSONB),
    Column("needs_review", Boolean, server_default="false"),
    Column("duplicate_of", Integer, ForeignKey("invoices.id")),
    Column("payment_terms", String(50)),
    Column("created_by", Integer, ForeignKey("users.id")),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime),
    Column("updated_by", Integer, ForeignKey("users.id")),
    Column("deleted_at", DateTime),
    Column("deleted_by", Integer),
    UniqueConstraint("customer_id", "supplier_id", "invoice_number", name="invoices_customer_id_supplier_id_invoice_number_key"),
    CheckConstraint("document_type IN ('invoice', 'receipt', 'other')", name="invoices_document_type_check"),
    CheckConstraint("status IN ('pending', 'approved', 'exported', 'rejected')", name="invoices_status_check"),
)

Index("idx_invoices_customer_date", invoices.c.customer_id, invoices.c.invoice_date)
Index("idx_invoices_supplier", invoices.c.supplier_id)
Index("idx_invoices_status", invoices.c.status)
Index("idx_invoices_needs_review", invoices.c.needs_review, postgresql_where=invoices.c.needs_review == True)

