"""Initial schema"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "series",
        sa.Column("code", sa.String(length=10), primary_key=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
    )
    op.create_table(
        "series_counters",
        sa.Column("series_code", sa.String(length=10), sa.ForeignKey("series.code"), primary_key=True),
        sa.Column("last_folio", sa.Integer(), nullable=False, default=0),
    )
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("serie", sa.String(length=10), nullable=False),
        sa.Column("folio", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=64)),
        sa.Column("facturama_id", sa.String(length=64)),
        sa.Column("issue_date", sa.Date()),
        sa.Column("excel_filename", sa.String(length=255)),
        sa.Column("request_json", sa.Text()),
        sa.Column("response_json", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("xml_path", sa.String(length=255)),
        sa.Column("pdf_path", sa.String(length=255)),
    )
    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("product_code", sa.String(length=50)),
        sa.Column("description", sa.String(length=255)),
        sa.Column("unit_code", sa.String(length=20)),
        sa.Column("unit", sa.String(length=50)),
        sa.Column("quantity", sa.Numeric(18, 6)),
        sa.Column("unit_price", sa.Numeric(18, 6)),
        sa.Column("subtotal", sa.Numeric(18, 6)),
        sa.Column("tax_object", sa.String(length=10)),
        sa.Column("tax_total", sa.Numeric(18, 6)),
        sa.Column("total", sa.Numeric(18, 6)),
        sa.Column("identification_number", sa.String(length=100)),
    )
    op.create_index("ix_invoices_serie_folio", "invoices", ["serie", "folio"], unique=True)
    op.create_index("ix_invoices_created", "invoices", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_invoices_created", table_name="invoices")
    op.drop_index("ix_invoices_serie_folio", table_name="invoices")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("series_counters")
    op.drop_table("series")
