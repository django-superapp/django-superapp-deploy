import os
import inspect

def escape_registry_url(i):
    return i.replace("-", "_").replace(".", "_").replace("/", "_")

def get_chart_path(chart_name):
    """
    Generate an absolute path to a Helm chart based on the caller's location.
    
    Args:
        chart_name: The chart directory name (e.g., 'cert-manager')
        
    Returns:
        Absolute path to the chart
    """
    # Get the caller's file path
    caller_frame = inspect.stack()[1]
    caller_file = caller_frame.filename
    caller_dir = os.path.dirname(os.path.abspath(caller_file))
    
    # Build the absolute path to the chart
    chart_path = os.path.join(caller_dir, chart_name)

    return chart_path
