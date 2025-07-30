#!/usr/bin/env python3

"""
Quick test script to verify GitHub Actions automation is working

This script runs basic tests and provides a simple way to verify your setup.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def check_environment():
    """Check if the environment is properly set up"""
    print("🔍 Checking environment...")
    
    # Check if we're in the right directory
    required_files = ['run_github_action.py', 'setup_github_config.py', 'single_run.py']
    missing_files = []
    
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing files: {', '.join(missing_files)}")
        print("   Please run this script from the python_statevector_simulation directory")
        return False
    
    print("✅ All required files found")
    
    # Check Python requirements
    try:
        import requests
        print("✅ requests library available")
    except ImportError:
        print("❌ requests library not found")
        print("   Install with: pip install requests")
        return False
    
    # Check for GitHub token
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("⚠️  GITHUB_TOKEN environment variable not set")
        print("   This is required for GitHub API access")
        print("   Set with: export GITHUB_TOKEN='your_token_here'")
        return False
    
    print(f"✅ GitHub token found (length: {len(token)})")
    return True

def run_setup_test():
    """Run the setup test"""
    print("\n🧪 Running setup test...")
    
    try:
        result = subprocess.run(
            ['python3', 'setup_github_config.py', '--test-token'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ Setup test passed")
            print("Output preview:")
            lines = result.stdout.split('\n')[:10]
            for line in lines:
                if line.strip():
                    print(f"   {line}")
            return True
        else:
            print("❌ Setup test failed")
            print("stderr:", result.stderr)
            return False
    
    except subprocess.TimeoutExpired:
        print("❌ Setup test timed out")
        return False
    except Exception as e:
        print(f"❌ Error running setup test: {e}")
        return False

def show_usage_examples():
    """Show practical usage examples"""
    print("\n📚 Usage Examples")
    print("=================")
    
    examples = [
        {
            "name": "Test your GitHub setup",
            "command": "python3 setup_github_config.py"
        },
        {
            "name": "Quick test simulation (small)",
            "command": "python3 run_github_action.py --N 8 --T 50 --circuit-realizations 2 --L 2"
        },
        {
            "name": "Production simulation",
            "command": "python3 run_github_action.py --N 14 --T 1000 --circuit-realizations 10 --L 3"
        },
        {
            "name": "Fire and forget (no monitoring)",
            "command": "python3 run_github_action.py --N 12 --T 500 --circuit-realizations 5 --L 2 --monitor false"
        },
        {
            "name": "Interactive examples",
            "command": "python3 example_usage.py"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['name']}:")
        print(f"   {example['command']}")

def main():
    print("🚀 GitHub Actions Automation - Quick Test")
    print("==========================================")
    
    # Check environment
    if not check_environment():
        print("\n❌ Environment check failed. Please fix the issues above.")
        sys.exit(1)
    
    print("\n✅ Environment check passed!")
    
    # Check if user wants to run the setup test
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        token = os.getenv('GITHUB_TOKEN')
        if token:
            run_setup_test()
        else:
            print("⚠️  Skipping setup test (no GITHUB_TOKEN)")
    
    # Show usage examples
    show_usage_examples()
    
    print("\n🎯 Next Steps:")
    print("1. If you haven't set up your GitHub token:")
    print("   export GITHUB_TOKEN='your_token_here'")
    print("2. Test your setup:")
    print("   python3 setup_github_config.py")
    print("3. Run a quick test:")
    print("   python3 run_github_action.py --N 8 --T 50 --circuit-realizations 2 --L 2")
    print("4. Or try the interactive examples:")
    print("   python3 example_usage.py")
    
    print("\n📖 For detailed documentation, see: README_github_automation.md")

if __name__ == '__main__':
    main()
