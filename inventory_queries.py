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