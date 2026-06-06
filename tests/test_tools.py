# tests/test_tools.py
# Unit tests for the three MCP tools
# Run with: python -m pytest tests/ -v

import sys
from pathlib import Path

# Add parent directory to path so we can import server
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import read_record, save_report, search_documents


# ═══════════════════════════════════════════════
# search_documents tests
# ═══════════════════════════════════════════════

class TestSearchDocuments:

    def test_finds_existing_term(self):
        """Should find 'damaged' in at least one document."""
        result = search_documents("damaged")
        assert "Found" in result
        assert "return_policy.txt" in result

    def test_finds_return_policy(self):
        """Should find return policy content."""
        result = search_documents("return")
        assert "return_policy.txt" in result
        assert "30 days" in result

    def test_finds_shipping_policy(self):
        """Should find shipping policy content."""
        result = search_documents("shipping")
        assert "shipping_policy.txt" in result

    def test_multiword_query_finds_results(self):
        """Multi-word query should match any word."""
        result = search_documents("damaged return refund")
        assert "Found" in result

    def test_empty_query_returns_error(self):
        """Empty query should return a clear error."""
        result = search_documents("")
        assert "ERROR" in result

    def test_no_results_returns_clear_message(self):
        """Query with no matches should say no results found."""
        result = search_documents("xyznonexistentterm123")
        assert "No results found" in result
        assert "Do not guess" in result

    def test_very_long_query_returns_error(self):
        """Query over 200 chars should return error."""
        result = search_documents("x" * 201)
        assert "ERROR" in result

    def test_source_name_in_result(self):
        """Results should always include the source filename."""
        result = search_documents("payment")
        assert "[Source:" in result
        assert ".txt]" in result


# ═══════════════════════════════════════════════
# read_record tests
# ═══════════════════════════════════════════════

class TestReadRecord:

    def test_finds_existing_order(self):
        """Should return correct data for ORD-1001."""
        result = read_record("ORD-1001")
        assert "Brightfield Logistics" in result
        assert "Heavy Duty Shelving Unit" in result
        assert "Delivered" in result

    def test_finds_ord_1005(self):
        """Should return correct data for ORD-1005."""
        result = read_record("ORD-1005")
        assert "ORD-1005" in result
        assert "Safety Helmet" in result
        assert "Delivered" in result
        assert "[Source: records.csv" in result

    def test_finds_pending_order(self):
        """Should return pending order correctly."""
        result = read_record("ORD-1014")
        assert "Pending" in result
        assert "Greenway Partners" in result

    def test_case_insensitive(self):
        """Should work with lowercase order ID."""
        result = read_record("ord-1005")
        assert "Safety Helmet" in result

    def test_nonexistent_order_returns_clear_message(self):
        """Non-existent order should say not found."""
        result = read_record("ORD-9999")
        assert "No record found" in result
        assert "Do not guess" in result

    def test_invalid_format_returns_error(self):
        """Wrong format should return clear error."""
        result = read_record("INVALID-123")
        assert "ERROR" in result
        assert "ORD-" in result

    def test_empty_id_returns_error(self):
        """Empty string should return error."""
        result = read_record("")
        assert "ERROR" in result

    def test_source_in_result(self):
        """Result should cite records.csv as source."""
        result = read_record("ORD-1001")
        assert "records.csv" in result


# ═══════════════════════════════════════════════
# save_report tests
# ═══════════════════════════════════════════════

class TestSaveReport:

    def test_saves_report_successfully(self, tmp_path, monkeypatch):
        """Should save a report and return success message."""
        import server
        monkeypatch.setattr(server, "OUTPUT_DIR", tmp_path)
        result = save_report("Test Report", "## Test\nThis is a test.")
        assert "Report saved successfully" in result
        assert ".md" in result

    def test_empty_title_returns_error(self):
        """Empty title should return error."""
        result = save_report("", "Some content")
        assert "ERROR" in result

    def test_empty_content_returns_error(self):
        """Empty content should return error."""
        result = save_report("Valid Title", "")
        assert "ERROR" in result

    def test_title_too_long_returns_error(self):
        """Title over 100 chars should return error."""
        result = save_report("x" * 101, "Some content")
        assert "ERROR" in result

    def test_content_too_long_returns_error(self):
        """Content over 50000 chars should return error."""
        result = save_report("Valid Title", "x" * 50001)
        assert "ERROR" in result

    def test_special_chars_in_title_handled(self, tmp_path, monkeypatch):
        """Special characters in title should be sanitized."""
        import server
        monkeypatch.setattr(server, "OUTPUT_DIR", tmp_path)
        result = save_report("Report: Test/2024", "## Content")
        assert "Report saved successfully" in result