import re

ORDER = [
    'Category',
    'Subcategory',
    'Supplier',
    'Location',
    'Department',
    'Employee',
    'Item',
    'Supply_Request'
]

def reorder(input, output, filepath = None):
    with open(input, 'r', encoding='utf-8') as f:
        content = f.read()

    if filepath:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read() + "\n" + content

    # Extract all INSERT INTO statement mapped by table name
    table_inserts = {table: [] for table in ORDER}

    pattern = re.compile(r'(INSERT\s+INTO\s+(\w+)\s*\(.*?\)\s*VALUES\s*.*?;)', re.DOTALL | re.IGNORECASE)

    for statement, table_name in pattern.findall(content):
        for key in ORDER:
            if table_name.strip().lower() == key.lower():
                table_inserts[key].append(statement.strip())
                break

    with open(output, 'w', encoding='utf-8') as out:
        out.write("BEGIN;\n\n")
        for table in ORDER:
            statement = table_inserts[table]
            if statement:
                out.write(f"----- \n")
                out.write(f"-- Table:{table}\n")
                out.write(f"----- \n")
            else:
                print(f"No INSERT statement found for table: {table}")
        out.write("COMMIT;\n")
    print("Successfully generated scripts{output}")

reorder('insertion.sql', 'order_insertion.sql', filepath='lookup_tables.sql')