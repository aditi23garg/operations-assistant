import pytest
import os
from pathlib import Path
from server import search_documents, read_record, save_report, OUTPUT_DIR

def test_read_record_valid():
    """Test reading a valid order ID"""
    result = read_record("ORD-1005")
    assert "ORD-1005" in result
    assert "Brightfield Logistics" in result
    assert "Safety Helmet" in result

def test_read_record_invalid():
    """Test reading an invalid order ID"""
    result = read_record("INVALID-ID")
    assert "not a valid order ID format" in result

def test_read_record_not_found():
    """Test reading an order ID that doesn't exist"""
    result = read_record("ORD-9999")
    assert "No record found" in result

def test_search_documents_valid():
    """Test searching for a valid keyword"""
    result = search_documents("damaged")
    assert "Found" in result
    assert "Source:" in result

def test_search_documents_no_results():
    """Test searching for a keyword that doesn't exist"""
    result = search_documents("supercalifragilisticexpialidocious")
    assert "No results found" in result

def test_save_report():
    """Test saving a report"""
    title = "Test Report"
    content = "# Test Content"
    result = save_report(title, content)
    
    assert "Report saved successfully" in result
    
    # Check if a file was actually created
    saved_files = list(OUTPUT_DIR.glob("*_Test_Report.md"))
    assert len(saved_files) > 0
    
    # Clean up the test file
    for f in saved_files:
        f.unlink()
