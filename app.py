"""Corporate Inventory & Supply Chain Management System — Streamlit Frontend."""

from __future__ import annotations

import datetime as dt

import altair as alt
import pandas as pd
import streamlit as st

from data_service import (
    CSV_PATH,
    InventoryService,
    default_pg_config,
    load_csv_data,
    test_pg_connection,
)

st.set_page_config(
    page_title="Corporate Inventory & Supply Chain",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def get_cached_csv() -> pd.DataFrame:
    return load_csv_data(CSV_PATH)


def render_csv_download(df: pd.DataFrame, filename: str, label: str = "Download CSV") -> None:
    if df.empty:
        return
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )


def init_sidebar() -> tuple[InventoryService, str]:
    """Render sidebar data source + PostgreSQL connection controls."""
    st.sidebar.title("📦 Inventory Console")
    st.sidebar.caption("CS 5493/4243 • Corporate Inventory & Supply Chain")

    if "pg_config" not in st.session_state:
        st.session_state.pg_config = default_pg_config()
    if "pg_connected" not in st.session_state:
        ok, msg = test_pg_connection(st.session_state.pg_config)
        st.session_state.pg_connected = ok
        st.session_state.pg_status_msg = msg
    if "data_mode" not in st.session_state:
        st.session_state.data_mode = (
            "PostgreSQL (Live DB)" if st.session_state.pg_connected else "CSV Preview (Office_Inventory.csv)"
        )

    mode_choice = st.sidebar.radio(
        "Data Source",
        options=["PostgreSQL (Live DB)", "CSV Preview (Office_Inventory.csv)"],
        key="data_mode",
    )

    with st.sidebar.expander("PostgreSQL Connection", expanded=(mode_choice == "PostgreSQL (Live DB)" and not st.session_state.pg_connected)):
        cfg = st.session_state.pg_config
        host = st.text_input("Host", value=cfg["host"])
        port = st.number_input("Port", min_value=1, max_value=65535, value=int(cfg["port"]), step=1)
        dbname = st.text_input("Database", value=cfg["dbname"])
        user = st.text_input("User", value=cfg["user"])
        password = st.text_input("Password", value=cfg["password"], type="password")

        if st.button("Test & Connect", use_container_width=True, type="primary"):
            new_cfg = {
                "host": host.strip(),
                "port": int(port),
                "dbname": dbname.strip(),
                "user": user.strip(),
                "password": password,
            }
            st.session_state.pg_config = new_cfg
            ok, msg = test_pg_connection(new_cfg)
            st.session_state.pg_connected = ok
            st.session_state.pg_status_msg = msg
            if ok:
                st.rerun()

    if st.session_state.pg_connected:
        st.sidebar.success(st.session_state.pg_status_msg)
    else:
        st.sidebar.warning(f"PostgreSQL unavailable: {st.session_state.pg_status_msg}")

    if mode_choice == "PostgreSQL (Live DB)":
        if not st.session_state.pg_connected:
            st.warning(
                "PostgreSQL is not connected yet. Enter your database credentials in the sidebar and click **Test & Connect**, or switch to **CSV Preview** to explore the dataset immediately."
            )
            st.stop()
        return InventoryService(mode="postgres", pg_config=st.session_state.pg_config), "postgres"

    csv_df = get_cached_csv()
    st.sidebar.info(f"Loaded `{CSV_PATH.name}` ({len(csv_df):,} rows)")
    return InventoryService(mode="csv", csv_df=csv_df), "csv"


def render_kpis(service: InventoryService) -> None:
    kpis = service.get_overview_kpis()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total SKUs", f"{int(kpis['total_skus']):,}")
    c2.metric("Units On Hand", f"{int(kpis['total_units']):,}")
    c3.metric("Inventory Value", f"${float(kpis['total_value_usd']):,.2f}")
    c4.metric(
        "At / Below Reorder",
        f"{int(kpis['low_or_out_count']):,}",
        delta=f"{int(kpis['out_of_stock_count']):,} out of stock",
        delta_color="inverse",
    )
    c5.metric(
        "Supply Requests",
        f"{int(kpis['total_requests']):,}",
        delta=f"{int(kpis['pending_requests']):,} pending",
        delta_color="off",
    )


def render_overview_tab(service: InventoryService) -> None:
    st.subheader("System Overview")
    stock_df, req_df = service.get_status_breakdowns()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Inventory by Stock Status")
        if not stock_df.empty:
            chart = (
                alt.Chart(stock_df)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("stock_status:N", title="Stock Status", sort="-y"),
                    y=alt.Y("item_count:Q", title="Item Count"),
                    color=alt.Color(
                        "stock_status:N",
                        scale=alt.Scale(
                            domain=["In Stock", "Low Stock", "Out of Stock"],
                            range=["#16A34A", "#D97706", "#DC2626"],
                        ),
                        legend=None,
                    ),
                    tooltip=[
                        alt.Tooltip("stock_status:N", title="Status"),
                        alt.Tooltip("item_count:Q", title="Items", format=","),
                        alt.Tooltip("total_value_usd:Q", title="Value (USD)", format="$,.2f"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(chart, use_container_width=True)

    with col2:
        st.markdown("#### Supply Requests by Status")
        if not req_df.empty:
            chart = (
                alt.Chart(req_df)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("request_status:N", title="Request Status", sort="-y"),
                    y=alt.Y("request_count:Q", title="Requests"),
                    color=alt.Color(
                        "request_status:N",
                        scale=alt.Scale(
                            domain=["Pending", "Approved", "Fulfilled", "Rejected"],
                            range=["#D97706", "#2563EB", "#16A34A", "#64748B"],
                        ),
                        legend=None,
                    ),
                    tooltip=[
                        alt.Tooltip("request_status:N", title="Status"),
                        alt.Tooltip("request_count:Q", title="Requests", format=","),
                        alt.Tooltip("total_units:Q", title="Total Units", format=","),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(chart, use_container_width=True)

    st.markdown("#### Top 10 Categories by Inventory Value")
    cat_summary = service.run_inventory_summary(group_by="Category", stock_status=None, min_value=0.0).head(10)
    if not cat_summary.empty:
        top_chart = (
            alt.Chart(cat_summary)
            .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color="#1F6FEB")
            .encode(
                y=alt.Y("group_name:N", sort="-x", title="Category"),
                x=alt.X("total_inventory_value_usd:Q", title="Total Inventory Value (USD)"),
                tooltip=[
                    alt.Tooltip("group_name:N", title="Category"),
                    alt.Tooltip("item_count:Q", title="Items", format=","),
                    alt.Tooltip("total_units_on_hand:Q", title="Units", format=","),
                    alt.Tooltip("total_inventory_value_usd:Q", title="Total Value", format="$,.2f"),
                ],
            )
            .properties(height=340)
        )
        st.altair_chart(top_chart, use_container_width=True)

    st.markdown("#### Item Catalog Explorer")
    search = st.text_input("Search by Item ID, Item Name, or Category", placeholder="e.g. ITEM-0001, Bookcase, Furniture")
    catalog_df = service.get_items_catalog(search=search, limit=200)
    st.dataframe(
        catalog_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "unit_cost_usd": st.column_config.NumberColumn("Unit Cost", format="$%.2f"),
            "inventory_value_usd": st.column_config.NumberColumn("Inventory Value", format="$%.2f"),
        },
    )


def render_inventory_summary_tab(service: InventoryService) -> None:
    st.subheader("Inventory Summary & Valuation")
    st.caption("Backed by `inventory_summary(connection, group_by, stock_status, min_value)`")

    f1, f2, f3 = st.columns(3)
    with f1:
        group_by = st.radio("Group By", options=["Category", "Location"], horizontal=True)
    with f2:
        status_opt = st.selectbox("Stock Status", options=["All", "In Stock", "Low Stock", "Out of Stock"])
        stock_status = None if status_opt == "All" else status_opt
    with f3:
        min_value = st.number_input("Minimum Total Value (USD)", min_value=0.0, value=0.0, step=500.0)

    df = service.run_inventory_summary(group_by=group_by, stock_status=stock_status, min_value=float(min_value))
    if df.empty:
        st.info("No groups matched the selected filters.")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Groups Matched", f"{len(df):,}")
    m2.metric("Total Units", f"{int(df['total_units_on_hand'].sum()):,}")
    m3.metric("Total Value", f"${float(df['total_inventory_value_usd'].sum()):,.2f}")

    top_n = st.slider("Chart Top N Groups", min_value=5, max_value=min(50, max(5, len(df))), value=min(15, len(df)))
    chart_df = df.head(top_n)
    chart = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color="#0EA5E9")
        .encode(
            y=alt.Y("group_name:N", sort="-x", title=group_by),
            x=alt.X("total_inventory_value_usd:Q", title="Total Inventory Value (USD)"),
            tooltip=[
                alt.Tooltip("group_name:N", title=group_by),
                alt.Tooltip("item_count:Q", title="Items", format=","),
                alt.Tooltip("total_units_on_hand:Q", title="Units On Hand", format=","),
                alt.Tooltip("total_inventory_value_usd:Q", title="Total Value", format="$,.2f"),
                alt.Tooltip("avg_unit_cost_usd:Q", title="Avg Unit Cost", format="$,.2f"),
            ],
        )
        .properties(height=max(260, min(520, top_n * 26)))
    )
    st.altair_chart(chart, use_container_width=True)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "group_name": group_by,
            "item_count": st.column_config.NumberColumn("Items", format="%d"),
            "total_units_on_hand": st.column_config.NumberColumn("Units On Hand", format="%d"),
            "total_inventory_value_usd": st.column_config.NumberColumn("Total Value (USD)", format="$%.2f"),
            "avg_unit_cost_usd": st.column_config.NumberColumn("Avg Unit Cost (USD)", format="$%.2f"),
        },
    )
    render_csv_download(df, f"inventory_summary_{group_by.lower()}.csv")


def render_low_stock_tab(service: InventoryService) -> None:
    st.subheader("Low Stock Alerts by Location")
    st.caption("Backed by `low_stock(connection, location_id)` — items where `QuantityOnHand <= ReorderLevel`.")

    locations = service.get_locations()
    if not locations:
        st.info("No locations found.")
        return

    loc_labels = [f"{loc_id} — {loc_name}" for loc_id, loc_name in locations]
    selected_idx = st.selectbox("Select Location", range(len(locations)), format_func=lambda i: loc_labels[i])
    location_id, location_name = locations[selected_idx]

    df = service.run_low_stock(location_id)
    if df.empty:
        st.success(f"No low-stock items at **{location_name}** ({location_id}).")
        return

    df["reorder_deficit"] = (df["reorder_level"] - df["quantity_on_hand"]).clip(lower=0)

    c1, c2, c3 = st.columns(3)
    c1.metric("Items Requiring Attention", f"{len(df):,}")
    c2.metric("Zero-Stock Items", f"{int((df['quantity_on_hand'] == 0).sum()):,}")
    c3.metric("Total Units Below Reorder", f"{int(df['reorder_deficit'].sum()):,}")

    melted = df.head(20).melt(
        id_vars=["item_name"],
        value_vars=["quantity_on_hand", "reorder_level"],
        var_name="metric",
        value_name="units",
    )
    chart = (
        alt.Chart(melted)
        .mark_bar()
        .encode(
            y=alt.Y("item_name:N", title="Item", sort="-x"),
            x=alt.X("units:Q", title="Units"),
            color=alt.Color(
                "metric:N",
                scale=alt.Scale(domain=["quantity_on_hand", "reorder_level"], range=["#DC2626", "#94A3B8"]),
                title="Metric",
            ),
            tooltip=["item_name:N", "metric:N", "units:Q"],
        )
        .properties(height=max(240, min(480, len(df.head(20)) * 26)))
    )
    st.altair_chart(chart, use_container_width=True)

    st.dataframe(df, use_container_width=True, hide_index=True)
    render_csv_download(df, f"low_stock_{location_id}.csv")


def render_track_requests_tab(service: InventoryService, mode: str) -> None:
    st.subheader("Supply Requests Tracker")
    st.caption("Backed by `track_requests(connection, department, employee)`")

    departments = service.get_departments()
    c1, c2 = st.columns(2)
    with c1:
        dept_choice = st.selectbox("Department", options=["All Departments"] + departments)
        department = None if dept_choice == "All Departments" else dept_choice
    with c2:
        employees = service.get_employees(department=department)
        emp_choice = st.selectbox("Employee", options=["All Employees"] + employees)
        employee = None if emp_choice == "All Employees" else emp_choice

    df = service.run_track_requests(department=department, employee=employee)

    if df.empty:
        st.info("No supply requests found for the selected filters.")
    else:
        counts = df["status"].value_counts().to_dict()
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Matching Requests", f"{len(df):,}")
        m2.metric("Pending", f"{counts.get('Pending', 0):,}")
        m3.metric("Approved", f"{counts.get('Approved', 0):,}")
        m4.metric("Fulfilled", f"{counts.get('Fulfilled', 0):,}")
        m5.metric("Rejected", f"{counts.get('Rejected', 0):,}")

        st.dataframe(df, use_container_width=True, hide_index=True)
        render_csv_download(df, "supply_requests.csv")

    if mode == "postgres":
        st.divider()
        op1, op2 = st.columns(2)
        with op1:
            with st.expander("➕ Submit New Supply Request"):
                catalog = service.get_items_catalog(limit=2500)
                all_emps = service.get_employees()
                if not catalog.empty and all_emps:
                    item_options = [f"{r['item_id']} — {r['item_name']}" for _, r in catalog.iterrows()]
                    with st.form("create_request_form"):
                        item_sel = st.selectbox("Item", options=item_options)
                        emp_sel = st.selectbox("Submitted By Employee", options=all_emps)
                        qty = st.number_input("Requested Quantity", min_value=1, value=1, step=1)
                        req_date = st.date_input("Request Date", value=dt.date.today())
                        submitted = st.form_submit_button("Create Request", type="primary")
                        if submitted:
                            item_id = item_sel.split(" — ", 1)[0]
                            try:
                                new_id = service.create_supply_request(item_id, emp_sel, int(qty), req_date)
                                st.success(f"Created Supply Request **{new_id}**.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Failed to create request: {exc}")

        with op2:
            with st.expander("✏️ Update Existing Request Status"):
                if not df.empty:
                    req_ids = df["request_id"].tolist()
                    with st.form("update_status_form"):
                        target_id = st.selectbox("Request ID", options=req_ids)
                        new_status = st.selectbox("New Status", options=["Pending", "Approved", "Fulfilled", "Rejected"])
                        updated = st.form_submit_button("Update Status")
                        if updated:
                            try:
                                service.update_supply_request_status(target_id, new_status)
                                st.success(f"Updated **{target_id}** to **{new_status}**.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Failed to update status: {exc}")


def render_most_requested_tab(service: InventoryService) -> None:
    st.subheader("Most Requested Items by Date Range")
    st.caption("Backed by `most_requested(connection, start_date, end_date)`")

    min_d, max_d = service.get_date_bounds()
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        start_date = st.date_input("Start Date", value=min_d, min_value=dt.date(2020, 1, 1), max_value=dt.date(2030, 12, 31))
    with c2:
        end_date = st.date_input("End Date", value=max_d, min_value=dt.date(2020, 1, 1), max_value=dt.date(2030, 12, 31))
    with c3:
        top_n = st.number_input("Top N Items", min_value=5, max_value=100, value=15, step=5)

    if start_date > end_date:
        st.error("Start Date must be on or before End Date.")
        return

    df = service.run_most_requested(start_date, end_date)
    if df.empty:
        st.info("No supply requests found in the selected date range.")
        return

    m1, m2 = st.columns(2)
    m1.metric("Unique Items Requested", f"{len(df):,}")
    m2.metric("Total Units Requested", f"{int(df['total_units_requested'].sum()):,}")

    top_df = df.head(int(top_n))
    chart = (
        alt.Chart(top_df)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color="#2563EB")
        .encode(
            y=alt.Y("item_name:N", sort="-x", title="Item"),
            x=alt.X("total_units_requested:Q", title="Total Units Requested"),
            tooltip=[
                alt.Tooltip("item_id:N", title="Item ID"),
                alt.Tooltip("item_name:N", title="Item"),
                alt.Tooltip("total_units_requested:Q", title="Units Requested", format=","),
            ],
        )
        .properties(height=max(260, min(560, len(top_df) * 26)))
    )
    st.altair_chart(chart, use_container_width=True)

    st.dataframe(df, use_container_width=True, hide_index=True)
    render_csv_download(df, f"most_requested_{start_date}_{end_date}.csv")


def render_sourcing_tab(service: InventoryService) -> None:
    st.subheader("Supplier Sourcing Breakdown")
    st.caption("Backed by `sourcing_supplies(connection, supplier_id, group_by)`")

    suppliers = service.get_suppliers()
    sup_options = [("ALL", "All Suppliers")] + suppliers

    c1, c2 = st.columns(2)
    with c1:
        sel_idx = st.selectbox(
            "Supplier",
            range(len(sup_options)),
            format_func=lambda i: sup_options[i][1] if sup_options[i][0] == "ALL" else f"{sup_options[i][0]} — {sup_options[i][1]}",
        )
        supplier_id = None if sup_options[sel_idx][0] == "ALL" else sup_options[sel_idx][0]
    with c2:
        group_by = st.radio("Group By", options=["Subcategory", "Category"], horizontal=True)

    df = service.run_sourcing_supplies(supplier_id=supplier_id, group_by=group_by)
    if df.empty:
        st.info("No sourcing data matched the selected filters.")
        return

    grp_col = "subcategory" if group_by == "Subcategory" else "category"

    m1, m2, m3 = st.columns(3)
    m1.metric("Rows / Groupings", f"{len(df):,}")
    m2.metric("Total SKUs", f"{int(df['sku_count'].sum()):,}")
    m3.metric("Total Sourcing Value", f"${float(df['total_sourcing_value_usd'].sum()):,.2f}")

    top_sup = (
        df.groupby("supplier_name", as_index=False)["total_sourcing_value_usd"]
        .sum()
        .sort_values("total_sourcing_value_usd", ascending=False)
        .head(15)
    )
    chart = (
        alt.Chart(top_sup)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color="#10B981")
        .encode(
            y=alt.Y("supplier_name:N", sort="-x", title="Supplier"),
            x=alt.X("total_sourcing_value_usd:Q", title="Total Sourcing Value (USD)"),
            tooltip=[
                alt.Tooltip("supplier_name:N", title="Supplier"),
                alt.Tooltip("total_sourcing_value_usd:Q", title="Sourcing Value", format="$,.2f"),
            ],
        )
        .properties(height=max(220, min(420, len(top_sup) * 26)))
    )
    st.altair_chart(chart, use_container_width=True)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            grp_col: group_by,
            "avg_unit_cost_usd": st.column_config.NumberColumn("Avg Unit Cost", format="$%.2f"),
            "total_sourcing_value_usd": st.column_config.NumberColumn("Total Sourcing Value", format="$%.2f"),
        },
    )
    render_csv_download(df, f"sourcing_supplies_{group_by.lower()}.csv")


def main() -> None:
    service, mode = init_sidebar()

    st.title("Corporate Inventory & Supply Chain Management")
    badge = "🟢 Live PostgreSQL (`inventory_queries.py`)" if mode == "postgres" else "🟡 CSV Preview Mode (`Office_Inventory.csv`)"
    st.caption(f"Mode: {badge}")

    render_kpis(service)
    st.divider()

    tabs = st.tabs(
        [
            "📊 Overview & Catalog",
            "💰 Inventory Summary",
            "⚠️ Low Stock Alerts",
            "📋 Supply Requests",
            "🔥 Most Requested",
            "🚚 Supplier Sourcing",
        ]
    )

    with tabs[0]:
        render_overview_tab(service)
    with tabs[1]:
        render_inventory_summary_tab(service)
    with tabs[2]:
        render_low_stock_tab(service)
    with tabs[3]:
        render_track_requests_tab(service, mode)
    with tabs[4]:
        render_most_requested_tab(service)
    with tabs[5]:
        render_sourcing_tab(service)


if __name__ == "__main__":
    main()
