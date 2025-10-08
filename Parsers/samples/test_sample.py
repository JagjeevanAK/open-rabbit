"""
Test sample file for pipeline analysis - approximately 200 lines
Contains various Python constructs to test AST, CFG, and PDG analysis
"""

import os
import sys
import json
import time
from typing import List, Dict, Optional, Any
from pathlib import Path
from collections import defaultdict

# Global constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
CONFIG_FILE = "config.json"

class ConfigError(Exception):
    """Custom exception for configuration errors"""
    pass

class DataProcessor:
    """Main data processing class with various methods"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or CONFIG_FILE
        self.config = {}
        self.cache = defaultdict(list)
        self.retry_count = 0
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            if not os.path.exists(self.config_path):
                raise ConfigError(f"Config file not found: {self.config_path}")
            
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
                
            return self.config
            
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ConfigError(f"Failed to load config: {e}")
    
    def validate_input(self, data: Any) -> bool:
        """Validate input data"""
        if data is None:
            return False
        
        if isinstance(data, str):
            return len(data.strip()) > 0
        elif isinstance(data, (list, dict)):
            return len(data) > 0
        elif isinstance(data, (int, float)):
            return data >= 0
        
        return True
    
    def process_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of items with error handling"""
        results = []
        
        for i, item in enumerate(items):
            try:
                if not self.validate_input(item):
                    continue
                
                # Simulate complex processing
                processed_item = self._transform_item(item, i)
                
                if processed_item:
                    results.append(processed_item)
                    self.cache[item.get('category', 'default')].append(processed_item)
                
            except Exception as e:
                print(f"Error processing item {i}: {e}")
                continue
        
        return results
    
    def _transform_item(self, item: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
        """Transform individual item"""
        result = {}
        
        # Complex conditional logic
        if item.get('type') == 'text':
            result['processed_text'] = self._process_text(item.get('content', ''))
        elif item.get('type') == 'number':
            result['processed_number'] = self._process_number(item.get('value', 0))
        elif item.get('type') == 'list':
            result['processed_list'] = self._process_list(item.get('items', []))
        else:
            result['processed_generic'] = str(item)
        
        # Add metadata
        result['index'] = index
        result['timestamp'] = self._get_timestamp()
        result['checksum'] = self._calculate_checksum(str(item))
        
        return result if result else None
    
    def _process_text(self, text: str) -> str:
        """Process text content"""
        if not text:
            return ""
        
        # Clean and normalize
        cleaned = text.strip().lower()
        
        # Apply transformations
        if len(cleaned) > 100:
            return cleaned[:100] + "..."
        
        return cleaned
    
    def _process_number(self, value: float) -> float:
        """Process numeric values"""
        if value < 0:
            return 0.0
        elif value > 1000:
            return 1000.0
        
        return round(value * 1.1, 2)
    
    def _process_list(self, items: List[Any]) -> List[Any]:
        """Process list items"""
        result = []
        
        for item in items:
            if isinstance(item, str):
                result.append(item.upper())
            elif isinstance(item, (int, float)):
                result.append(item * 2)
            else:
                result.append(str(item))
        
        return result[:10]  # Limit to 10 items
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        import time
        return str(int(time.time()))
    
    def _calculate_checksum(self, data: str) -> str:
        """Calculate simple checksum"""
        return str(hash(data) % 10000)
    
    def retry_operation(self, operation, *args, **kwargs):
        """Retry operation with exponential backoff"""
        for attempt in range(MAX_RETRIES):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise e
                
                wait_time = 2 ** attempt
                print(f"Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        return None

def load_data_from_file(file_path: str) -> List[Dict[str, Any]]:
    """Load data from JSON file"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            return []
            
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return []
    except json.JSONDecodeError:
        print(f"Invalid JSON in file: {file_path}")
        return []

def save_results(results: List[Dict[str, Any]], output_path: str) -> bool:
    """Save processing results to file"""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Results saved to: {output_path}")
        return True
        
    except Exception as e:
        print(f"Failed to save results: {e}")
        return False

def main():
    """Main execution function"""
    # Initialize processor
    processor = DataProcessor()
    
    try:
        # Load configuration
        config = processor.load_config()
        input_file = config.get('input_file', 'data.json')
        output_file = config.get('output_file', 'results.json')
        
    except ConfigError as e:
        print(f"Configuration error: {e}")
        # Use defaults
        input_file = 'data.json'
        output_file = 'results.json'
    
    # Load and process data
    data = load_data_from_file(input_file)
    
    if not data:
        print("No data to process")
        return
    
    # Process in batches
    batch_size = 10
    all_results = []
    
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        batch_results = processor.process_batch(batch)
        all_results.extend(batch_results)
        
        print(f"Processed batch {i // batch_size + 1}, got {len(batch_results)} results")
    
    # Save results
    if all_results:
        success = save_results(all_results, output_file)
        if success:
            print(f"Processing complete! {len(all_results)} items processed.")
        else:
            print("Failed to save results")
    else:
        print("No results to save")

if __name__ == "__main__":
    main()