"""Data access layer for the Corporate Inventory & Supply Chain Management System.

Supports both:
1. Live PostgreSQL via psycopg2 + existing functions in ``inventory_queries.py``.
2. Local CSV preview mode via ``Office_Inventory.csv`` when a database is not connected.
"""

from __future__ import annotations

import datetime as dt
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2

import inventory_queries as iq

CSV_PATH = Path(__file__).resolve().parent / "Office_Inventory.csv"


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def rows_to_dataframe(rows: list[dict[str, Any]], numeric_cols: tuple[str, ...] = ()) -> pd.DataFrame:
    """Convert query result dicts into a pandas DataFrame with clean numeric types."""
    if not rows:
        return pd.DataFrame()
    cleaned = [{k: _normalize_value(v) for k, v in row.items()} for row in rows]
    df = pd.DataFrame(cleaned)
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def default_pg_config() -> dict[str, Any]:
    """Read default PostgreSQL connection parameters from environment variables."""
    port_raw = os.environ.get("PGPORT", "5432")
    try:
        port = int(port_raw)
    except ValueError:
        port = 5432
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": port,
        "dbname": os.environ.get("PGDATABASE", "postgres"),
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", ""),
    }


def open_pg_connection(cfg: dict[str, Any]):
    """Open a short-lived PostgreSQL connection using psycopg2."""
    return psycopg2.connect(
        host=cfg["host"],
        port=int(cfg["port"]),
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        connect_timeout=5,
    )


def test_pg_connection(cfg: dict[str, Any]) -> tuple[bool, str]:
    """Verify PostgreSQL connectivity and check whether the core tables exist."""
    try:
        with open_pg_connection(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN ('item', 'supply_request', 'location', 'supplier', 'department', 'employee', 'category', 'subcategory')
                    """
                )
                tables = {row[0] for row in cur.fetchall()}
                if "item" not in tables or "supply_request" not in tables:
                    return (
                        False,
                        "Connected to PostgreSQL, but schema tables (Item, Supply_Request) were not found in 'public'. Run schema.sql and insertion.sql first.",
                    )
                cur.execute("SELECT COUNT(*) FROM Item")
                item_count = cur.fetchone()[0]
                return True, f"Connected to {cfg['dbname']}@{cfg['host']}:{cfg['port']} ({item_count:,} items)"
    except Exception as exc:
        return False, str(exc).strip()


def load_csv_data(csv_path: Path = CSV_PATH) -> pd.DataFrame:
    """Load the local Office_Inventory.csv dataset for preview mode."""
    df = pd.read_csv(csv_path)
    df["RequestDate"] = pd.to_datetime(df["RequestDate"]).dt.date
    for col in ("QuantityOnHand", "ReorderLevel", "TargetStockLevel", "RequestedQuantity"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in ("EstimatedUnitCostUSD", "InventoryValueUSD"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


class InventoryService:
    """Unified interface over either PostgreSQL or the local CSV dataset."""

    def __init__(self, mode: str, pg_config: dict[str, Any] | None = None, csv_df: pd.DataFrame | None = None):
        self.mode = mode  # "postgres" or "csv"
        self.pg_config = pg_config or default_pg_config()
        self.csv_df = csv_df

    def _query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with open_pg_connection(self.pg_config) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [c[0] for c in cur.description]
                return [{k: _normalize_value(v) for k, v in zip(cols, row)} for row in cur.fetchall()]

    # --- Metadata & KPI Lookups ---

    def get_overview_kpis(self) -> dict[str, Any]:
        if self.mode == "postgres":
            item_stats = self._query_all(
                """
                SELECT COUNT(*) AS total_skus,
                       COALESCE(SUM(QuantityOnHand), 0) AS total_units,
                       ROUND(COALESCE(SUM(InventoryValueUSD), 0)::numeric, 2) AS total_value_usd,
                       COUNT(*) FILTER (WHERE QuantityOnHand <= ReorderLevel) AS low_or_out_count,
                       COUNT(*) FILTER (WHERE StockStatus = 'Out of Stock') AS out_of_stock_count
                FROM Item
                """
            )[0]
            req_stats = self._query_all(
                """
                SELECT COUNT(*) AS total_requests,
                       COUNT(*) FILTER (WHERE RequestStatus = 'Pending') AS pending_requests
                FROM Supply_Request
                """
            )[0]
            return {**item_stats, **req_stats}

        df = self.csv_df
        return {
            "total_skus": int(df["ItemID"].nunique()),
            "total_units": int(df["QuantityOnHand"].sum()),
            "total_value_usd": round(float(df["InventoryValueUSD"].sum()), 2),
            "low_or_out_count": int((df["QuantityOnHand"] <= df["ReorderLevel"]).sum()),
            "out_of_stock_count": int((df["StockStatus"] == "Out of Stock").sum()),
            "total_requests": int(df["RequestID"].nunique()),
            "pending_requests": int((df["RequestStatus"] == "Pending").sum()),
        }

    def get_status_breakdowns(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        if self.mode == "postgres":
            stock_df = rows_to_dataframe(
                self._query_all(
                    """
                    SELECT StockStatus AS stock_status,
                           COUNT(*) AS item_count,
                           ROUND(COALESCE(SUM(InventoryValueUSD), 0)::numeric, 2) AS total_value_usd
                    FROM Item
                    GROUP BY StockStatus
                    ORDER BY item_count DESC
                    """
                ),
                numeric_cols=("item_count", "total_value_usd"),
            )
            req_df = rows_to_dataframe(
                self._query_all(
                    """
                    SELECT RequestStatus AS request_status,
                           COUNT(*) AS request_count,
                           COALESCE(SUM(RequestedQuantity), 0) AS total_units
                    FROM Supply_Request
                    GROUP BY RequestStatus
                    ORDER BY request_count DESC
                    """
                ),
                numeric_cols=("request_count", "total_units"),
            )
            return stock_df, req_df

        df = self.csv_df
        stock_df = (
            df.groupby("StockStatus", as_index=False)
            .agg(item_count=("ItemID", "count"), total_value_usd=("InventoryValueUSD", "sum"))
            .rename(columns={"StockStatus": "stock_status"})
            .sort_values("item_count", ascending=False)
        )
        stock_df["total_value_usd"] = stock_df["total_value_usd"].round(2)

        req_df = (
            df.groupby("RequestStatus", as_index=False)
            .agg(request_count=("RequestID", "count"), total_units=("RequestedQuantity", "sum"))
            .rename(columns={"RequestStatus": "request_status"})
            .sort_values("request_count", ascending=False)
        )
        return stock_df, req_df

    def get_locations(self) -> list[tuple[str, str]]:
        if self.mode == "postgres":
            rows = self._query_all("SELECT LocationID, LocationName FROM Location ORDER BY LocationID")
            return [(r["locationid"], r["locationname"]) for r in rows]
        locs = self.csv_df[["LocationID", "LocationName"]].drop_duplicates().sort_values("LocationID")
        return list(zip(locs["LocationID"], locs["LocationName"]))

    def get_departments(self) -> list[str]:
        if self.mode == "postgres":
            rows = self._query_all("SELECT DepartmentName FROM Department ORDER BY DepartmentName")
            return [r["departmentname"] for r in rows]
        return sorted(self.csv_df["Department"].dropna().unique().tolist())

    def get_employees(self, department: str | None = None) -> list[str]:
        if self.mode == "postgres":
            if department:
                rows = self._query_all(
                    "SELECT EmployeeName FROM Employee WHERE DepartmentName = %s ORDER BY EmployeeName",
                    (department,),
                )
            else:
                rows = self._query_all("SELECT EmployeeName FROM Employee ORDER BY EmployeeName")
            return [r["employeename"] for r in rows]

        df = self.csv_df
        if department:
            df = df[df["Department"] == department]
        return sorted(df["Employee"].dropna().unique().tolist())

    def get_suppliers(self) -> list[tuple[str, str]]:
        if self.mode == "postgres":
            rows = self._query_all("SELECT SupplierID, SupplierName FROM Supplier ORDER BY SupplierName")
            return [(r["supplierid"], r["suppliername"]) for r in rows]
        sups = self.csv_df[["SupplierID", "SupplierName"]].drop_duplicates().sort_values("SupplierName")
        return list(zip(sups["SupplierID"], sups["SupplierName"]))

    def get_date_bounds(self) -> tuple[dt.date, dt.date]:
        if self.mode == "postgres":
            row = self._query_all("SELECT MIN(RequestDate) AS min_d, MAX(RequestDate) AS max_d FROM Supply_Request")[0]
            if row["min_d"] and row["max_d"]:
                return row["min_d"], row["max_d"]
        else:
            if not self.csv_df.empty:
                return self.csv_df["RequestDate"].min(), self.csv_df["RequestDate"].max()
        return dt.date(2026, 9, 1), dt.date(2026, 10, 19)

    def get_items_catalog(self, search: str = "", limit: int = 200) -> pd.DataFrame:
        if self.mode == "postgres":
            like_term = f"%{search.strip()}%"
            rows = self._query_all(
                """
                SELECT i.ItemID AS item_id,
                       i.ItemName AS item_name,
                       c.CategoryName AS category,
                       i.SubcategoryName AS subcategory,
                       l.LocationName AS location,
                       sup.SupplierName AS supplier,
                       i.QuantityOnHand AS quantity_on_hand,
                       i.ReorderLevel AS reorder_level,
                       i.TargetStockLevel AS target_stock_level,
                       i.EstimatedUnitCostUSD AS unit_cost_usd,
                       i.InventoryValueUSD AS inventory_value_usd,
                       i.StockStatus AS stock_status,
                       i.ManagedByEmployee AS managed_by
                FROM Item AS i
                JOIN Subcategory AS s ON i.SubcategoryName = s.SubcategoryName
                JOIN Category AS c ON s.CategoryName = c.CategoryName
                JOIN Location AS l ON i.LocationID = l.LocationID
                JOIN Supplier AS sup ON i.SupplierID = sup.SupplierID
                WHERE (%s = '' OR i.ItemName ILIKE %s OR i.ItemID ILIKE %s OR c.CategoryName ILIKE %s)
                ORDER BY i.ItemID
                LIMIT %s
                """,
                (search.strip(), like_term, like_term, like_term, limit),
            )
            return rows_to_dataframe(
                rows,
                numeric_cols=("quantity_on_hand", "reorder_level", "target_stock_level", "unit_cost_usd", "inventory_value_usd"),
            )

        df = self.csv_df
        q = search.strip().lower()
        if q:
            mask = (
                df["ItemName"].str.lower().str.contains(q, na=False)
                | df["ItemID"].str.lower().str.contains(q, na=False)
                | df["Category"].str.lower().str.contains(q, na=False)
            )
            df = df[mask]
        cols = {
            "ItemID": "item_id",
            "ItemName": "item_name",
            "Category": "category",
            "Subcategory": "subcategory",
            "LocationName": "location",
            "SupplierName": "supplier",
            "QuantityOnHand": "quantity_on_hand",
            "ReorderLevel": "reorder_level",
            "TargetStockLevel": "target_stock_level",
            "EstimatedUnitCostUSD": "unit_cost_usd",
            "InventoryValueUSD": "inventory_value_usd",
            "StockStatus": "stock_status",
            "Employee": "managed_by",
        }
        return df[list(cols.keys())].rename(columns=cols).sort_values("item_id").head(limit).reset_index(drop=True)

    # --- The 5 Core Course Project Queries (inventory_queries.py) ---

    def run_low_stock(self, location_id: str) -> pd.DataFrame:
        if self.mode == "postgres":
            with open_pg_connection(self.pg_config) as conn:
                rows = iq.low_stock(conn, location_id)
            return rows_to_dataframe(rows, numeric_cols=("quantity_on_hand", "reorder_level"))

        df = self.csv_df
        sub = df[(df["LocationID"] == location_id) & (df["QuantityOnHand"] <= df["ReorderLevel"])].copy()
        sub = sub[["ItemID", "ItemName", "LocationName", "QuantityOnHand", "ReorderLevel"]].rename(
            columns={
                "ItemID": "item_id",
                "ItemName": "item_name",
                "LocationName": "location",
                "QuantityOnHand": "quantity_on_hand",
                "ReorderLevel": "reorder_level",
            }
        )
        return sub.sort_values(["quantity_on_hand", "item_name", "item_id"]).reset_index(drop=True)

    def run_track_requests(self, department: str | None = None, employee: str | None = None) -> pd.DataFrame:
        if self.mode == "postgres":
            with open_pg_connection(self.pg_config) as conn:
                rows = iq.track_requests(conn, department=department, employee=employee)
            return rows_to_dataframe(rows, numeric_cols=("requested_quantity",))

        df = self.csv_df.copy()
        # Note: in CSV, RequestedByEmployee is the submitter and Employee/Department maps employee->department.
        emp_dept = df[["Employee", "Department"]].drop_duplicates().set_index("Employee")["Department"].to_dict()
        df["SubmitterDept"] = df["RequestedByEmployee"].map(emp_dept).fillna(df["Department"])
        if department:
            df = df[df["SubmitterDept"] == department]
        if employee:
            df = df[df["RequestedByEmployee"] == employee]
        out = df[
            ["RequestID", "RequestDate", "RequestedByEmployee", "SubmitterDept", "ItemName", "RequestedQuantity", "RequestStatus"]
        ].rename(
            columns={
                "RequestID": "request_id",
                "RequestDate": "request_date",
                "RequestedByEmployee": "employee",
                "SubmitterDept": "department",
                "ItemName": "item_name",
                "RequestedQuantity": "requested_quantity",
                "RequestStatus": "status",
            }
        )
        return out.sort_values(["request_date", "request_id"], ascending=[False, True]).reset_index(drop=True)

    def run_most_requested(self, start_date: dt.date, end_date: dt.date) -> pd.DataFrame:
        if self.mode == "postgres":
            with open_pg_connection(self.pg_config) as conn:
                rows = iq.most_requested(conn, start_date, end_date)
            return rows_to_dataframe(rows, numeric_cols=("total_units_requested",))

        df = self.csv_df
        sub = df[(df["RequestDate"] >= start_date) & (df["RequestDate"] <= end_date)]
        out = (
            sub.groupby(["ItemID", "ItemName"], as_index=False)["RequestedQuantity"]
            .sum()
            .rename(columns={"ItemID": "item_id", "ItemName": "item_name", "RequestedQuantity": "total_units_requested"})
            .sort_values(["total_units_requested", "item_id"], ascending=[False, True])
            .reset_index(drop=True)
        )
        return out

    def run_inventory_summary(
        self, group_by: str = "Category", stock_status: str | None = None, min_value: float = 0.0
    ) -> pd.DataFrame:
        if self.mode == "postgres":
            with open_pg_connection(self.pg_config) as conn:
                rows = iq.inventory_summary(conn, group_by=group_by, stock_status=stock_status, min_value=min_value)
            return rows_to_dataframe(
                rows,
                numeric_cols=("item_count", "total_units_on_hand", "total_inventory_value_usd", "avg_unit_cost_usd"),
            )

        df = self.csv_df
        if stock_status:
            df = df[df["StockStatus"] == stock_status]
        grp_col = "Category" if group_by == "Category" else "LocationName"
        out = (
            df.groupby(grp_col, as_index=False)
            .agg(
                item_count=("ItemID", "count"),
                total_units_on_hand=("QuantityOnHand", "sum"),
                total_inventory_value_usd=("InventoryValueUSD", "sum"),
                avg_unit_cost_usd=("EstimatedUnitCostUSD", "mean"),
            )
            .rename(columns={grp_col: "group_name"})
        )
        out["total_inventory_value_usd"] = out["total_inventory_value_usd"].round(2)
        out["avg_unit_cost_usd"] = out["avg_unit_cost_usd"].round(2)
        out = out[out["total_inventory_value_usd"] >= min_value]
        return out.sort_values(["total_inventory_value_usd", "group_name"], ascending=[False, True]).reset_index(drop=True)

    def run_sourcing_supplies(self, supplier_id: str | None = None, group_by: str = "Subcategory") -> pd.DataFrame:
        if self.mode == "postgres":
            with open_pg_connection(self.pg_config) as conn:
                rows = iq.sourcing_supplies(conn, supplier_id=supplier_id, group_by=group_by)
            return rows_to_dataframe(
                rows,
                numeric_cols=("sku_count", "total_units", "avg_unit_cost_usd", "total_sourcing_value_usd"),
            )

        df = self.csv_df
        if supplier_id:
            df = df[df["SupplierID"] == supplier_id]
        grp_col = "Subcategory" if group_by == "Subcategory" else "Category"
        grp_alias = "subcategory" if group_by == "Subcategory" else "category"
        out = (
            df.groupby(["SupplierID", "SupplierName", grp_col], as_index=False)
            .agg(
                sku_count=("ItemID", "count"),
                total_units=("QuantityOnHand", "sum"),
                avg_unit_cost_usd=("EstimatedUnitCostUSD", "mean"),
                total_sourcing_value_usd=("InventoryValueUSD", "sum"),
            )
            .rename(columns={"SupplierID": "supplier_id", "SupplierName": "supplier_name", grp_col: grp_alias})
        )
        out["avg_unit_cost_usd"] = out["avg_unit_cost_usd"].round(2)
        out["total_sourcing_value_usd"] = out["total_sourcing_value_usd"].round(2)
        return out.sort_values(["supplier_name", "total_sourcing_value_usd"], ascending=[True, False]).reset_index(drop=True)

    # --- Live PostgreSQL Operations ---

    def create_supply_request(self, item_id: str, employee_name: str, quantity: int, request_date: dt.date) -> str:
        """Insert a new Pending Supply_Request into PostgreSQL and return its generated RequestID."""
        if self.mode != "postgres":
            raise RuntimeError("Creating supply requests requires Live PostgreSQL mode.")
        with open_pg_connection(self.pg_config) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(MAX(CAST(SUBSTRING(RequestID FROM '([0-9]+)$') AS INT)), 0) + 1
                    FROM Supply_Request
                    WHERE RequestID ~ '^REQ-[0-9]+$'
                    """
                )
                next_num = cur.fetchone()[0]
                req_id = f"REQ-{next_num:04d}"
                cur.execute(
                    """
                    INSERT INTO Supply_Request (
                        RequestID, RequestDate, RequestStatus, RequestedQuantity, SubmittedByEmployee, ItemID
                    )
                    VALUES (%s, %s, 'Pending', %s, %s, %s)
                    """,
                    (req_id, request_date, int(quantity), employee_name, item_id),
                )
            conn.commit()
        return req_id

    def update_supply_request_status(self, request_id: str, new_status: str) -> None:
        """Update an existing Supply_Request status in PostgreSQL."""
        if self.mode != "postgres":
            raise RuntimeError("Updating request status requires Live PostgreSQL mode.")
        with open_pg_connection(self.pg_config) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE Supply_Request SET RequestStatus = %s WHERE RequestID = %s",
                    (new_status, request_id),
                )
            conn.commit()
