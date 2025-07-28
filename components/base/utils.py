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


def get_fleet_chart_url(chart_path, git_url="git@github.com:bringes/rke2-cluster", branch="main"):
    """
    Generate a Fleet-compatible git repository URL for a Helm chart.
    
    Args:
        chart_path: The relative path to the chart from the caller's location (e.g., './charts/rancher-monitoring-crd')
        git_url: The SSH git repository URL (defaults to current repo)
        branch: The git branch to reference (defaults to 'main')
        
    Returns:
        Fleet-compatible git URL in format: git@host:user/repo//path/to/chart?branch=branch
    """
    # Get the caller's file path to determine the component directory
    caller_frame = inspect.stack()[1]
    caller_file = caller_frame.filename
    caller_dir = os.path.dirname(os.path.abspath(caller_file))
    
    # Convert the relative chart path to an absolute path
    abs_chart_path = os.path.join(caller_dir, chart_path)
    
    # Find the repository root (where .git directory is)
    repo_root = caller_dir
    while repo_root != os.path.dirname(repo_root):  # Stop at filesystem root
        if os.path.exists(os.path.join(repo_root, '.git')):
            break
        repo_root = os.path.dirname(repo_root)
    
    # Calculate the relative path from repository root to the chart
    rel_path_from_repo = os.path.relpath(abs_chart_path, repo_root)
    
    # Convert Windows paths to Unix-style paths for git URLs
    rel_path_from_repo = rel_path_from_repo.replace(os.sep, '/')
    
    # Format as Fleet git URL: git_url//path?branch=branch
    fleet_url = f"{git_url}//{rel_path_from_repo}?branch={branch}"
    
    return fleet_url
