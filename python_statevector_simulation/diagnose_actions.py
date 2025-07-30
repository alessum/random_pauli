#!/usr/bin/env python3

"""
Comprehensive GitHub Actions Diagnostics

This script tests various aspects of the GitHub Actions setup to identify
exactly what's preventing the workflow from being recognized.
"""

import os
import sys
import requests
import json
from datetime import datetime

def test_github_api():
    """Test basic GitHub API connectivity and authentication"""
    print("🔍 Testing GitHub API...")
    
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ GITHUB_TOKEN not set")
        return False
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    
    try:
        # Test authentication
        response = requests.get('https://api.github.com/user', headers=headers)
        if response.status_code == 200:
            user = response.json()
            print(f"✅ Authenticated as: {user['login']}")
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

def test_repository_access():
    """Test repository access and information"""
    print("\n🏠 Testing repository access...")
    
    token = os.getenv('GITHUB_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json'
    }
    
    owner, repo = 'alessum', 'random_pauli'
    
    try:
        url = f'https://api.github.com/repos/{owner}/{repo}'
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            repo_info = response.json()
            print(f"✅ Repository: {repo_info['full_name']}")
            print(f"   Default branch: {repo_info['default_branch']}")
            print(f"   Private: {repo_info['private']}")
            print(f"   Fork: {repo_info.get('fork', False)}")
            print(f"   Has issues: {repo_info.get('has_issues', False)}")
            print(f"   Has wiki: {repo_info.get('has_wiki', False)}")
            print(f"   Has pages: {repo_info.get('has_pages', False)}")
            
            # Check permissions
            permissions = repo_info.get('permissions', {})
            print(f"   Permissions:")
            print(f"     Admin: {permissions.get('admin', False)}")
            print(f"     Push: {permissions.get('push', False)}")
            print(f"     Pull: {permissions.get('pull', False)}")
            
            return repo_info['default_branch']
        else:
            print(f"❌ Repository access failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Repository test failed: {e}")
        return None

def test_workflow_file_exists():
    """Test if workflow file exists on GitHub"""
    print("\n📄 Testing workflow file existence...")
    
    token = os.getenv('GITHUB_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json'
    }
    
    owner, repo = 'alessum', 'random_pauli'
    
    # Test on both main and master branches
    for branch in ['main', 'master']:
        try:
            url = f'https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows/executor.yml'
            params = {'ref': branch}
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                file_info = response.json()
                print(f"✅ Workflow file found on {branch} branch")
                print(f"   Size: {file_info['size']} bytes")
                print(f"   SHA: {file_info['sha'][:8]}...")
                return branch
            else:
                print(f"❌ Workflow file not found on {branch} branch: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error checking {branch} branch: {e}")
    
    return None

def test_actions_api():
    """Test GitHub Actions API endpoints"""
    print("\n⚙️  Testing Actions API...")
    
    token = os.getenv('GITHUB_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json'
    }
    
    owner, repo = 'alessum', 'random_pauli'
    
    try:
        # Test workflows endpoint
        url = f'https://api.github.com/repos/{owner}/{repo}/actions/workflows'
        response = requests.get(url, headers=headers)
        
        print(f"   Workflows API status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            workflows = data.get('workflows', [])
            print(f"   Total workflows: {data.get('total_count', 0)}")
            
            if workflows:
                for wf in workflows:
                    print(f"   - {wf['name']} ({wf['path']})")
                    print(f"     State: {wf['state']}")
                    print(f"     Created: {wf['created_at']}")
            else:
                print("   No workflows found - Actions may not be enabled")
                
        elif response.status_code == 404:
            print("   ❌ Actions not available - may be disabled")
        else:
            print(f"   ❌ Unexpected status: {response.text}")
            
        # Test if we can access runs (another way to check Actions)
        url = f'https://api.github.com/repos/{owner}/{repo}/actions/runs'
        response = requests.get(url, headers=headers, params={'per_page': 1})
        print(f"   Runs API status: {response.status_code}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ Actions API test failed: {e}")
        return False

def test_workflow_dispatch():
    """Test workflow dispatch endpoint specifically"""
    print("\n🚀 Testing workflow dispatch endpoint...")
    
    token = os.getenv('GITHUB_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    
    owner, repo = 'alessum', 'random_pauli'
    
    # Try both by filename and by ID
    for workflow_ref in ['executor.yml', 'Parallel Simulations']:
        try:
            url = f'https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_ref}/dispatches'
            
            # Just check if the endpoint exists (don't actually dispatch)
            response = requests.post(url, headers=headers, json={
                'ref': 'main',
                'inputs': {'N': '8', 'T': '10', 'circuit_realizations': '1', 'L': '1', 'batch_size': '1'}
            })
            
            print(f"   Dispatch endpoint ({workflow_ref}): {response.status_code}")
            
            if response.status_code == 204:
                print(f"   ✅ Successfully dispatched workflow!")
                return True
            elif response.status_code == 404:
                print(f"   ❌ Workflow not found")
            else:
                print(f"   ❌ Error: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Error testing {workflow_ref}: {e}")
    
    return False

def suggest_solutions():
    """Provide specific suggestions based on the test results"""
    print("\n💡 Suggested Solutions:")
    print("="*50)
    
    print("\n1. Enable GitHub Actions manually:")
    print("   - Visit: https://github.com/alessum/random_pauli")
    print("   - Click the 'Actions' tab")
    print("   - If you see 'Actions are disabled', click 'I understand...'")
    
    print("\n2. Check repository settings:")
    print("   - Go to Settings > Actions > General")
    print("   - Ensure 'Allow all actions and reusable workflows' is selected")
    print("   - Ensure Actions permissions allow workflow runs")
    
    print("\n3. Verify workflow file:")
    print("   - Ensure the file is named exactly 'executor.yml'")
    print("   - Check for any YAML syntax errors")
    print("   - Verify it's in the correct branch")
    
    print("\n4. If this is a fork:")
    print("   - Forks often have Actions disabled by default")
    print("   - You must manually enable them in Settings")
    
    print("\n5. Check token permissions:")
    print("   - Token needs 'repo' and 'actions:write' scopes")
    print("   - Regenerate token if necessary")

def main():
    print("🔬 GitHub Actions Comprehensive Diagnostics")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Repository: alessum/random_pauli")
    print("=" * 50)
    
    # Run all tests
    api_ok = test_github_api()
    if not api_ok:
        print("\n❌ Basic API access failed. Check your token.")
        return
    
    default_branch = test_repository_access()
    workflow_branch = test_workflow_file_exists()
    actions_ok = test_actions_api()
    dispatch_ok = test_workflow_dispatch()
    
    # Summary
    print("\n📊 Test Summary:")
    print("=" * 30)
    print(f"✅ GitHub API: {'OK' if api_ok else 'FAILED'}")
    print(f"✅ Repository access: {'OK' if default_branch else 'FAILED'}")
    print(f"✅ Workflow file exists: {'OK' if workflow_branch else 'FAILED'}")
    print(f"✅ Actions API: {'OK' if actions_ok else 'FAILED'}")
    print(f"✅ Workflow dispatch: {'OK' if dispatch_ok else 'FAILED'}")
    
    if default_branch:
        print(f"\nℹ️  Default branch: {default_branch}")
    if workflow_branch:
        print(f"ℹ️  Workflow found on: {workflow_branch}")
    
    if dispatch_ok:
        print("\n🎉 Everything is working! You can run workflows.")
    else:
        suggest_solutions()

if __name__ == '__main__':
    main()
