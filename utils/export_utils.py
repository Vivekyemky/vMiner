import pandas as pd
import json
import os
from datetime import datetime
from typing import List, Dict, Any

class ExportUtils:
    """Utility class for exporting data to various formats."""
    
    def __init__(self, export_dir: str = "exports"):
        self.export_dir = export_dir
        os.makedirs(export_dir, exist_ok=True)
    
    def export_to_csv(self, data: List[Dict[str, Any]]) -> str:
        """Export data to CSV file."""
        if not data:
            raise ValueError("No data to export")
        
        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{timestamp}.csv"
        filepath = os.path.join(self.export_dir, filename)
        
        df.to_csv(filepath, index=False)
        return filepath
    
    def export_to_json(self, data: List[Dict[str, Any]]) -> str:
        """Export data to JSON file."""
        if not data:
            raise ValueError("No data to export")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{timestamp}.json"
        filepath = os.path.join(self.export_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        return filepath
    
    def export_to_excel(self, data: List[Dict[str, Any]]) -> str:
        """Export data to Excel file."""
        if not data:
            raise ValueError("No data to export")
        
        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{timestamp}.xlsx"
        filepath = os.path.join(self.export_dir, filename)
        
        df.to_excel(filepath, index=False, engine='openpyxl')
        return filepath
