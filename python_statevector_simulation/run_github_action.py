#!/usr/bin/env python3

"""
Script to trigger the GitHub Actions workflow for Parallel Rydberg Simulations

This script uses the GitHub API to dispatch the workflow with custom parameters.
You need a GitHub token with 'actions:write' permissions.

Usage:
    python run_github_action.py --N 14 --T 1000 --circuit-realizations 10 --L 3 --batch-size 5
    
    # Or with environment variable for token:
    export GITHUB_TOKEN="your_token_here"
    python run_github_action.py --N 16 --T 500 --circuit-realizations 5 --L 4
"""

import os
import sys
import time
import json
import argparse
import requests
from datetime import datetime

GITHUB_API = "https://api.github.com"

def trigger_workflow(owner, repo, workflow_file, token, inputs):
    """
    Trigger a GitHub Actions workflow using workflow_dispatch event
    
    Args:
        owner: GitHub repository owner
        repo: Repository name
        workflow_file: Workflow filename (e.g., 'executor.yml')
        token: GitHub token with actions:write permission
        inputs: Dictionary of workflow inputs
    
    Returns:
        Response from GitHub API
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows/{workflow_file}/dispatches"
    
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    
    payload = {
        'ref': 'main',  # or 'master' depending on your default branch
        'inputs': inputs
    }
    
    print(f"🚀 Triggering workflow: {workflow_file}")
    print(f"📍 Repository: {owner}/{repo}")
    print(f"⚙️  Parameters:")
    for key, value in inputs.items():
        print(f"   {key}: {value}")
    print()
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        if response.status_code == 204:
            print("✅ Workflow triggered successfully!")
            return True
        else:
            print(f"⚠️  Unexpected response code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error triggering workflow: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response code: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return False

def get_recent_runs(owner, repo, workflow_file, token, limit=5):
    """
    Get recent workflow runs to monitor status
    
    Args:
        owner: GitHub repository owner
        repo: Repository name
        workflow_file: Workflow filename
        token: GitHub token
        limit: Number of recent runs to fetch
    
    Returns:
        List of recent workflow runs
    """
    try:
        # First get workflow ID
        workflows_url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows"
        headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
        }
        
        workflows_response = requests.get(workflows_url, headers=headers)
        workflows_response.raise_for_status()
        workflows = workflows_response.json().get('workflows', [])
        
        workflow_id = None
        for wf in workflows:
            if wf.get('path', '').endswith(f"/{workflow_file}"):
                workflow_id = wf['id']
                break
        
        if not workflow_id:
            print(f"❌ Workflow '{workflow_file}' not found")
            return []
        
        # Get recent runs
        runs_url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        params = {'per_page': limit}
        
        runs_response = requests.get(runs_url, headers=headers, params=params)
        runs_response.raise_for_status()
        
        return runs_response.json().get('workflow_runs', [])
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching workflow runs: {e}")
        return []

def monitor_workflow(owner, repo, workflow_file, token, timeout_minutes=30):
    """
    Monitor the most recent workflow run
    
    Args:
        owner: GitHub repository owner
        repo: Repository name
        workflow_file: Workflow filename
        token: GitHub token
        timeout_minutes: Maximum time to wait for completion
    """
    print(f"🔍 Monitoring workflow runs (timeout: {timeout_minutes} minutes)...")
    print("Press Ctrl+C to stop monitoring\n")
    
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    
    try:
        while time.time() - start_time < timeout_seconds:
            runs = get_recent_runs(owner, repo, workflow_file, token, limit=1)
            
            if not runs:
                print("⚠️  No workflow runs found")
                time.sleep(30)
                continue
            
            run = runs[0]
            status = run.get('status', 'unknown')
            conclusion = run.get('conclusion', 'none')
            created_at = run.get('created_at', '')
            html_url = run.get('html_url', '')
            
            # Parse the creation time
            try:
                created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                created_str = created_time.strftime('%Y-%m-%d %H:%M:%S UTC')
            except:
                created_str = created_at
            
            print(f"📊 Status: {status.upper():<12} | Conclusion: {conclusion.upper():<10} | Created: {created_str}")
            print(f"🔗 URL: {html_url}")
            
            if status == 'completed':
                if conclusion == 'success':
                    print("\n🎉 Workflow completed successfully!")
                    return True
                else:
                    print(f"\n❌ Workflow failed with conclusion: {conclusion}")
                    return False
            
            print("⏳ Waiting 30 seconds before next check...\n")
            time.sleep(30)
        
        print(f"\n⏰ Monitoring timeout reached ({timeout_minutes} minutes)")
        return False
        
    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped by user")
        return False

def validate_inputs(args):
    """Validate input parameters"""
    if args.N <= 0:
        raise ValueError("N must be positive")
    if args.T <= 0:
        raise ValueError("T must be positive")
    if args.circuit_realizations <= 0:
        raise ValueError("circuit-realizations must be positive")
    if args.L <= 0:
        raise ValueError("L must be positive")
    if args.batch_size <= 0:
        raise ValueError("batch-size must be positive")

def main():
    parser = argparse.ArgumentParser(
        description="Trigger GitHub Actions workflow for Parallel Rydberg Simulations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_github_action.py --N 14 --T 1000 --circuit-realizations 10 --L 3
  python run_github_action.py --N 16 --T 500 --circuit-realizations 5 --L 4 --batch-size 10
  python run_github_action.py --owner myuser --repo myrepo --N 12 --T 800 --monitor false
        """
    )
    
    # GitHub repository settings
    parser.add_argument('--owner', default='alessum', help='GitHub repository owner')
    parser.add_argument('--repo', default='random_pauli', help='Repository name') 
    parser.add_argument('--workflow', default='executor.yml', help='Workflow filename')
    parser.add_argument('--token', help='GitHub token (or set GITHUB_TOKEN env var)')
    
    # Workflow parameters
    parser.add_argument('--N', type=int, required=True, help='Number of qubits')
    parser.add_argument('--T', type=int, required=True, help='Time to run')
    parser.add_argument('--circuit-realizations', type=int, required=True, 
                       help='Total circuit realizations (cr dimension)')
    parser.add_argument('--L', type=int, required=True, 
                       help='Grid resolution (L × L for Jx×Jz)')
    parser.add_argument('--batch-size', type=int, default=5,
                       help='Number of (cr,ix,iz) points per job')
    
    # Monitoring options
    parser.add_argument('--monitor', choices=['true', 'false'], default='true',
                       help='Monitor workflow execution')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Monitoring timeout in minutes')
    
    args = parser.parse_args()
    
    # Validate inputs
    try:
        validate_inputs(args)
    except ValueError as e:
        print(f"❌ Invalid input: {e}")
        sys.exit(1)
    
    # Get GitHub token
    token = args.token or os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ GitHub token required. Provide via --token or GITHUB_TOKEN environment variable")
        print("   Get a token at: https://github.com/settings/tokens")
        print("   Required permissions: repo, actions:write")
        sys.exit(1)
    
    # Prepare workflow inputs (all must be strings for GitHub API)
    inputs = {
        'N': str(args.N),
        'T': str(args.T),
        'circuit_realizations': str(args.circuit_realizations),
        'L': str(args.L),
        'batch_size': str(args.batch_size)
    }
    
    # Trigger the workflow
    success = trigger_workflow(args.owner, args.repo, args.workflow, token, inputs)
    
    if not success:
        sys.exit(1)
    
    # Monitor if requested
    if args.monitor == 'true':
        print("⏱️  Waiting 10 seconds for workflow to start...")
        time.sleep(10)
        monitor_workflow(args.owner, args.repo, args.workflow, token, args.timeout)
    else:
        print("ℹ️  Monitoring disabled. Check workflow status at:")
        print(f"   https://github.com/{args.owner}/{args.repo}/actions")

if __name__ == '__main__':
    main()
