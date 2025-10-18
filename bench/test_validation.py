#!/usr/bin/env python3
"""
Simple validation test for implemented features
"""
import sys
import json
import time

def test_io_monitoring():
    """Test I/O monitoring functionality"""
    print("Testing I/O monitoring...")
    try:
        sys.path.append('.')
        from io_monitor import IOMonitor, run_fio_baseline
        
        # Test fio baseline
        print("Running fio baseline test...")
        baseline = run_fio_baseline()
        print(f"Baseline results: {json.dumps(baseline, indent=2)}")
        
        # Test IOMonitor class
        print("Testing IOMonitor class...")
        monitor = IOMonitor()
        monitor.start_monitoring()
        time.sleep(2)
        monitor.stop_monitoring()
        
        print("✅ I/O monitoring test passed")
        return True
    except Exception as e:
        print(f"❌ I/O monitoring test failed: {e}")
        return False

def test_cache_flushing():
    """Test page cache flushing"""
    print("Testing page cache flushing...")
    try:
        sys.path.append('.')
        from utils import flush_page_cache
        
        flush_page_cache()
        print("✅ Cache flushing test passed")
        return True
    except Exception as e:
        print(f"❌ Cache flushing test failed: {e}")
        return False

def test_qdrant_connection():
    """Test Qdrant connection"""
    print("Testing Qdrant connection...")
    try:
        sys.path.append('.')
        from qdrant_helper import connect
        
        client = connect()
        collections = client.get_collections()
        print(f"✅ Qdrant connection test passed - Collections: {collections}")
        return True
    except Exception as e:
        print(f"❌ Qdrant connection test failed: {e}")
        return False

def test_weaviate_connection():
    """Test Weaviate connection"""  
    print("Testing Weaviate connection...")
    try:
        sys.path.append('.')
        from weaviate_client import connect
        
        client = connect()
        print("✅ Weaviate connection test passed")
        return True
    except Exception as e:
        print(f"❌ Weaviate connection test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Validation Test Suite ===\n")
    
    tests = [
        test_io_monitoring,
        test_cache_flushing,  
        test_qdrant_connection,
        test_weaviate_connection
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All tests passed! Implementation is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the error messages above.")