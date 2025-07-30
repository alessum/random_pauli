#!/usr/bin/env python3

"""
Configuration and testing script for GitHub Actions automation

This script helps you:
1. Test your GitHub token
2. Verify repository access
3. List available workflows
4. Run a test workflow dispatch

Usage:
    python setup_github_config.py --test-token
    python setup_github_config.py --list-workflows
    python setup_github_config.py --test-dispatch --N 12 --T 100 --circuit-realizations 2 --L 2
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime

GITHUB_API = "https://api.github.com"

def test_token(token, owner, repo):
    """Test if the GitHub token has the required permissions"""
    print("🔑 Testing GitHub token...")
    
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
    }
    
    try:
        # Test basic repository access
        repo_url = f"{GITHUB_API}/repos/{owner}/{repo}"
        response = requests.get(repo_url, headers=headers)
        
        if response.status_code == 200:
            repo_data = response.json()
            print(f"✅ Repository access: {repo_data['full_name']}")
            print(f"   Description: {repo_data.get('description', 'No description')}")
            print(f"   Private: {repo_data['private']}")
        elif response.status_code == 404:
            print(f"❌ Repository {owner}/{repo} not found or no access")
            return False
        else:
            print(f"❌ Repository access failed: {response.status_code}")
            return False
        
        # Test actions access
        actions_url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows"
        response = requests.get(actions_url, headers=headers)
        
        if response.status_code == 200:
            workflows = response.json().get('workflows', [])
            print(f"✅ Actions access: Found {len(workflows)} workflows")
        else:
            print(f"❌ Actions access failed: {response.status_code}")
            print("   Make sure your token has 'actions:write' permission")
            return False
        
        # Test user info
        user_url = f"{GITHUB_API}/user"
        response = requests.get(user_url, headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Token owner: {user_data['login']} ({user_data.get('name', 'No name')})")
        
        print("🎉 Token test successful!")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False

def list_workflows(token, owner, repo):
    """List all available workflows in the repository"""
    print("📋 Listing available workflows...")
    
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
    }
    
    try:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        workflows = response.json().get('workflows', [])
        
        if not workflows:
            print("❌ No workflows found")
            return False
        
        print(f"Found {len(workflows)} workflow(s):")
        print()
        
        for i, wf in enumerate(workflows, 1):
            name = wf.get('name', 'Unnamed')
            path = wf.get('path', 'Unknown path')
            state = wf.get('state', 'unknown')
            created = wf.get('created_at', '')
            
            print(f"{i}. {name}")
            print(f"   Path: {path}")
            print(f"   State: {state}")
            print(f"   Created: {created}")
            print()
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error listing workflows: {e}")
        return False

def get_workflow_inputs(token, owner, repo, workflow_file):
    """Get the input schema for a specific workflow"""
    print(f"🔍 Getting workflow inputs for {workflow_file}...")
    
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
    }
    
    try:
        # Get workflow content
        url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/.github/workflows/{workflow_file}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        content_data = response.json()
        if content_data.get('type') != 'file':
            print(f"❌ {workflow_file} is not a file")
            return False
        
        print(f"✅ Found workflow file: {workflow_file}")
        print(f"   Size: {content_data.get('size', 0)} bytes")
        print(f"   Last modified: {content_data.get('last_modified', 'Unknown')}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error getting workflow: {e}")
        return False

def test_dispatch(token, owner, repo, workflow_file, inputs):
    """Test workflow dispatch (dry run)"""
    print("🧪 Testing workflow dispatch...")
    print("📋 Would dispatch with inputs:")
    for key, value in inputs.items():
        print(f"   {key}: {value}")
    
    # Just test the endpoint without actually dispatching
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows/{workflow_file}/dispatches"
    print(f"🔗 Dispatch URL: {url}")
    
    # Check if workflow file exists
    return get_workflow_inputs(token, owner, repo, workflow_file)

def save_config(owner, repo, workflow_file):
    """Save configuration to a file"""
    config = {
        'owner': owner,
        'repo': repo,
        'workflow': workflow_file,
        'configured_at': datetime.now().isoformat()
    }
    
    config_file = 'github_config.json'
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"💾 Configuration saved to {config_file}")

def load_config():
    """Load configuration from file"""
    config_file = 'github_config.json'
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    return {}

def main():
    parser = argparse.ArgumentParser(
        description="Setup and test GitHub Actions configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Configuration
    parser.add_argument('--owner', default='alessum', help='GitHub repository owner')
    parser.add_argument('--repo', default='random_pauli', help='Repository name')
    parser.add_argument('--workflow', default='executor.yml', help='Workflow filename')
    parser.add_argument('--token', help='GitHub token (or set GITHUB_TOKEN env var)')
    
    # Actions
    parser.add_argument('--test-token', action='store_true', help='Test GitHub token')
    parser.add_argument('--list-workflows', action='store_true', help='List available workflows')
    parser.add_argument('--test-dispatch', action='store_true', help='Test workflow dispatch (dry run)')
    parser.add_argument('--save-config', action='store_true', help='Save configuration to file')
    
    # Test dispatch parameters
    parser.add_argument('--N', type=int, default=12, help='Number of qubits (for test)')
    parser.add_argument('--T', type=int, default=100, help='Time steps (for test)')
    parser.add_argument('--circuit-realizations', type=int, default=2, help='Circuit realizations (for test)')
    parser.add_argument('--L', type=int, default=2, help='Grid resolution (for test)')
    parser.add_argument('--batch-size', type=int, default=2, help='Batch size (for test)')
    
    args = parser.parse_args()
    
    # Load existing config
    config = load_config()
    
    # Use config values as defaults
    owner = args.owner or config.get('owner', 'alessum')
    repo = args.repo or config.get('repo', 'quera_proj')
    workflow_file = args.workflow or config.get('workflow', 'executor.yml')
    
    # Get token
    token = args.token or os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ GitHub token required. Set GITHUB_TOKEN environment variable or use --token")
        print("   Get a token at: https://github.com/settings/tokens")
        print("   Required scopes: repo, actions:write")
        sys.exit(1)
    
    print(f"🎯 Target repository: {owner}/{repo}")
    print(f"🔧 Workflow file: {workflow_file}")
    print()
    
    success = True
    
    # Run tests based on arguments
    if args.test_token:
        success &= test_token(token, owner, repo)
        print()
    
    if args.list_workflows:
        success &= list_workflows(token, owner, repo)
        print()
    
    if args.test_dispatch:
        inputs = {
            'N': str(args.N),
            'T': str(args.T),
            'circuit_realizations': str(args.circuit_realizations),
            'L': str(args.L),
            'batch_size': str(args.batch_size)
        }
        success &= test_dispatch(token, owner, repo, workflow_file, inputs)
        print()
    
    if args.save_config:
        save_config(owner, repo, workflow_file)
    
    # Default action if no specific action requested
    if not any([args.test_token, args.list_workflows, args.test_dispatch, args.save_config]):
        print("🚀 Running all tests...")
        success &= test_token(token, owner, repo)
        print()
        success &= list_workflows(token, owner, repo)
        print()
        
        if success:
            print("✅ All tests passed! You're ready to use run_github_action.py")
        else:
            print("❌ Some tests failed. Please check your configuration.")
            sys.exit(1)

if __name__ == '__main__':
    main()
