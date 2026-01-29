#!/usr/bin/env python3

from datetime import datetime

def show_current_datetime():
    """Display the current date and time."""
    try:
        # Get current datetime
        current_dt = datetime.now()
        
        # Format and display the datetime
        formatted_dt = current_dt.strftime("%Y-%m-%d %H:%M:%S")
        print(f"Current date and time: {formatted_dt}")
        
    except Exception as e:
        print(f"Error getting current datetime: {e}")

if __name__ == "__main__":
    show_current_datetime()