# Low stock
# WIll show items that are below their reorder level at a specific location 

def low_stock(connection, location_id):
    sql = """
        SELECT i.ItemID AS item_id,
               i.ItemName AS item_name,
               l.LocationName AS location,
               i.QuantityOnHand AS quantity_on_hand,
               i.ReorderLevel AS reorder_level
        FROM Item AS i
        JOIN Location AS l ON i.LocationID = l.LocationID
        WHERE l.LocationID = %s
          AND i.QuantityOnHand <= i.ReorderLevel
        ORDER BY i.QuantityOnHand, i.ItemName, i.ItemID
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, (location_id,))
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


# Supply request
#  Filters requests by the employee, department or both

def track_requests(connection, department=None, employee=None):
    sql = """
        SELECT r.RequestID AS request_id,
               r.RequestDate AS request_date,
               e.EmployeeName AS employee,
               d.DepartmentName AS department,
               i.ItemName AS item_name,
               r.RequestedQuantity AS requested_quantity,
               r.RequestStatus AS status
        FROM Supply_Request AS r
        JOIN Employee AS e ON r.SubmittedByEmployee = e.EmployeeName
        JOIN Department AS d ON e.DepartmentName = d.DepartmentName
        JOIN Item AS i ON r.ItemID = i.ItemID
        WHERE (%s::text IS NULL OR d.DepartmentName = %s)
          AND (%s::text IS NULL OR e.EmployeeName = %s)
        ORDER BY r.RequestDate DESC, r.RequestID
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, (department, department, employee, employee))
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


# Most requested items 
# puts items by their total units requested in the selected range

def most_requested(connection, start_date, end_date):
    sql = """
        SELECT i.ItemID AS item_id,
               i.ItemName AS item_name,
               SUM(r.RequestedQuantity) AS total_units_requested
        FROM Supply_Request AS r
        JOIN Item AS i ON r.ItemID = i.ItemID
        WHERE r.RequestDate BETWEEN %s AND %s
        GROUP BY i.ItemID, i.ItemName
        ORDER BY total_units_requested DESC, i.ItemID
    """

    with connection.cursor() as cursor: 
        cursor.execute(sql, (start_date, end_date))
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

#Inventory Summary and Evaluation by Location or Category

def inventory_summary(connection, group_by="Category", stock_status=None, min_value=0.0):
    if group_by == "Category":
        select_col = "c.CategoryName AS group_name"
        group_col = "c.CategoryName"
    else:
        select_col = "l.LocationName AS group_name"
        group_col = "l.LocationName"

    sql = f"""
        SELECT {select_col},
               COUNT(i.ItemID) AS item_count,
               COALESCE(SUM(i.QuantityOnHand), 0) AS total_units_on_hand,
               ROUND(COALESCE(SUM(i.InventoryValueUSD), 0)::numeric, 2) AS total_inventory_value_usd,
               ROUND(COALESCE(AVG(i.EstimatedUnitCostUSD), 0)::numeric, 2) AS avg_unit_cost_usd
        FROM Item AS i
        JOIN Subcategory AS s ON i.SubcategoryName = s.SubcategoryName
        JOIN Category AS c ON s.CategoryName = c.CategoryName
        JOIN Location AS l ON i.LocationID = l.LocationID
        WHERE (%s::text IS NULL OR i.StockStatus = %s)
        GROUP BY {group_col}
        HAVING COALESCE(SUM(i.InventoryValueUSD), 0) >= %s
        ORDER BY total_inventory_value_usd DESC, group_name ASC
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, (stock_status, stock_status, min_value))
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


# Sourcing Supplies Breakdown 
def sourcing_supplies(connection, supplier_id=None, group_by="Subcategory"):

    grp_field = "s.SubcategoryName" if group_by == "Subcategory" else "c.CategoryName"
    grp_alias = "subcategory" if group_by == "Subcategory" else "category"

    sql = f"""
        SELECT sup.SupplierID AS supplier_id,
               sup.SupplierName AS supplier_name,
               {grp_field} AS {grp_alias},
               COUNT(i.ItemID) AS sku_count,
               COALESCE(SUM(i.QuantityOnHand), 0) AS total_units,
               ROUND(COALESCE(AVG(i.EstimatedUnitCostUSD), 0)::numeric, 2) AS avg_unit_cost_usd,
               ROUND(COALESCE(SUM(i.InventoryValueUSD), 0)::numeric, 2) AS total_sourcing_value_usd
        FROM Item AS i
        JOIN Supplier AS sup ON i.SupplierID = sup.SupplierID
        JOIN Subcategory AS s ON i.SubcategoryName = s.SubcategoryName
        JOIN Category AS c ON s.CategoryName = c.CategoryName
        WHERE (%s::text IS NULL OR sup.SupplierID = %s)
        GROUP BY sup.SupplierID, sup.SupplierName, {grp_field}
        ORDER BY sup.SupplierName ASC, total_sourcing_value_usd DESC
    """

    with connection.cursor() as cursor:
        cursor.execute(sql, (supplier_id, supplier_id))
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]