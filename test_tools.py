# test_tools.py
# Quick manual test — imports tool functions directly and calls them

from server import search_documents, read_record, save_report

print("=" * 50)
print("TEST 1: search_documents")
print("=" * 50)
result = search_documents("return policy")
print(result)

print("\n" + "=" * 50)
print("TEST 2: read_record")
print("=" * 50)
result = read_record("ORD-1005")
print(result)

print("\n" + "=" * 50)
print("TEST 3: save_report")
print("=" * 50)
result = save_report(
    title="Test Report",
    content="## Test\nThis is a test report.\n\n[Source: records.csv]"
)
print(result)

print("\n" + "=" * 50)
print("TEST 4: bad inputs (validation check)")
print("=" * 50)
print(search_documents(""))          # should return ERROR
print(read_record("INVALID-999"))    # should return ERROR
print(read_record("ORD-9999"))       # should return 'not found'