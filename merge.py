files_to_merge = ['lookup_tables.sql', 'my_4_tables.sql', 'ethan_inserts.sql']

with open('insertion.sql', 'w', encoding='utf-8') as outfile:
    outfile.write("BEGIN;\n\n")
    for file_name in files_to_merge:
        with open(file_name, 'r', encoding='utf-8') as infile:
            outfile.write(infile.read().strip() + "\n\n")
    outfile.write("COMMIT;\n")

print("Successfully merged into 'insertion.sql'!")