#!/usr/bin/env python3

"""
Example usage script demonstrating how to use the GitHub Actions automation tools

This script shows various examples of how to:
1. Set up and test your GitHub configuration
2. Run GitHub Actions workflows programmatically
3. Monitor workflow execution

Prerequisites:
1. Set up your GitHub token: export GITHUB_TOKEN="your_token_here"
2. Make sure your repository settings are correct in the scripts

Examples included:
- Quick test run (small parameters)
- Production run (larger parameters)
- Batch of different configurations
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle output"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Command completed successfully")
        if result.stdout:
            print("Output:")
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed with exit code {e.returncode}")
        if e.stdout:
            print("stdout:")
            print(e.stdout)
        if e.stderr:
            print("stderr:")
            print(e.stderr)
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        return False

def check_token():
    """Check if GitHub token is available"""
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ GITHUB_TOKEN environment variable not set")
        print("   Get a token at: https://github.com/settings/tokens")
        print("   Required scopes: repo, actions:write")
        print("\n   Set it with: export GITHUB_TOKEN='your_token_here'")
        return False
    
    print(f"✅ GitHub token found (length: {len(token)})")
    return True

def example_1_setup_and_test():
    """Example 1: Set up and test GitHub configuration"""
    print("\n🚀 EXAMPLE 1: Setup and Test GitHub Configuration")
    print("This will test your GitHub token and list available workflows")
    
    if not check_token():
        return False
    
    # Test the GitHub token and configuration
    cmd = ["python3", "setup_github_config.py", "--test-token", "--list-workflows"]
    return run_command(cmd, "Testing GitHub token and listing workflows")

def example_2_quick_test():
    """Example 2: Quick test run with small parameters"""
    print("\n🚀 EXAMPLE 2: Quick Test Run")
    print("This will run a small simulation for testing purposes")
    
    if not check_token():
        return False
    
    # Small test parameters
    cmd = [
        "python3", "run_github_action.py",
        "--N", "8",                      # Small number of qubits
        "--T", "50",                     # Short time
        "--circuit-realizations", "2",   # Few realizations  
        "--L", "2",                      # Small grid
        "--batch-size", "2",             # Small batches
        "--timeout", "15"                # Short timeout
    ]
    
    return run_command(cmd, "Running quick test simulation")

def example_3_production_run():
    """Example 3: Production run with realistic parameters"""
    print("\n🚀 EXAMPLE 3: Production Run")
    print("This will run a more realistic simulation")
    
    if not check_token():
        return False
    
    # Production parameters
    cmd = [
        "python3", "run_github_action.py",
        "--N", "14",                     # Moderate number of qubits
        "--T", "1000",                   # Longer time evolution
        "--circuit-realizations", "10",  # More circuit realizations
        "--L", "4",                      # Larger parameter grid
        "--batch-size", "8",             # Efficient batch size
        "--timeout", "60"                # Longer timeout
    ]
    
    return run_command(cmd, "Running production simulation")

def example_4_no_monitoring():
    """Example 4: Fire and forget (no monitoring)"""
    print("\n🚀 EXAMPLE 4: Fire and Forget")
    print("This will trigger a workflow without monitoring")
    
    if not check_token():
        return False
    
    cmd = [
        "python3", "run_github_action.py",
        "--N", "12",
        "--T", "500", 
        "--circuit-realizations", "5",
        "--L", "3",
        "--monitor", "false"             # No monitoring
    ]
    
    return run_command(cmd, "Triggering workflow without monitoring")

def example_5_custom_repository():
    """Example 5: Using custom repository settings"""
    print("\n🚀 EXAMPLE 5: Custom Repository")
    print("This shows how to use different repository settings")
    
    if not check_token():
        return False
    
    cmd = [
        "python3", "run_github_action.py",
        "--owner", "your-username",      # Replace with your GitHub username
        "--repo", "your-repository",     # Replace with your repository name
        "--workflow", "executor.yml",    # Workflow filename
        "--N", "10",
        "--T", "200",
        "--circuit-realizations", "3",
        "--L", "2",
        "--monitor", "false"
    ]
    
    print("⚠️  Note: This example uses placeholder repository settings.")
    print("   Update --owner and --repo to match your actual repository.")
    print(f"   Command would be: {' '.join(cmd)}")
    return True

def example_6_batch_runs():
    """Example 6: Running multiple configurations"""
    print("\n🚀 EXAMPLE 6: Batch Runs")
    print("This shows how to run multiple different configurations")
    
    if not check_token():
        return False
    
    # Different configurations to test
    configs = [
        {"N": 8, "T": 100, "cr": 2, "L": 2, "desc": "Small test"},
        {"N": 10, "T": 200, "cr": 3, "L": 2, "desc": "Medium test"},
        {"N": 12, "T": 500, "cr": 5, "L": 3, "desc": "Large test"},
    ]
    
    for i, config in enumerate(configs, 1):
        print(f"\n--- Configuration {i}/3: {config['desc']} ---")
        
        cmd = [
            "python3", "run_github_action.py",
            "--N", str(config["N"]),
            "--T", str(config["T"]),
            "--circuit-realizations", str(config["cr"]),
            "--L", str(config["L"]),
            "--monitor", "false"  # Don't monitor each one
        ]
        
        success = run_command(cmd, f"Running {config['desc']}")
        if not success:
            print(f"❌ Configuration {i} failed, stopping batch")
            return False
        
        # Small delay between submissions
        if i < len(configs):
            print("⏳ Waiting 5 seconds before next submission...")
            time.sleep(5)
    
    print("\n✅ All batch configurations submitted!")
    return True

def main():
    """Main function with menu"""
    print("🎯 GitHub Actions Automation Examples")
    print("=====================================")
    
    # Check if we're in the right directory
    if not Path("setup_github_config.py").exists():
        print("❌ Please run this script from the python_statevector_simulation directory")
        sys.exit(1)
    
    examples = [
        ("Setup and Test", example_1_setup_and_test),
        ("Quick Test Run", example_2_quick_test),
        ("Production Run", example_3_production_run),
        ("Fire and Forget", example_4_no_monitoring),
        ("Custom Repository", example_5_custom_repository),
        ("Batch Runs", example_6_batch_runs),
    ]
    
    # Show menu
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    print("  0. Run all setup examples (1-2)")
    print("  q. Quit")
    
    try:
        choice = input("\nEnter your choice (0-6, q): ").strip().lower()
        
        if choice == 'q':
            print("👋 Goodbye!")
            return
        
        if choice == '0':
            # Run setup examples
            print("\n🔄 Running setup examples...")
            example_1_setup_and_test()
            time.sleep(2)
            example_2_quick_test()
            return
        
        try:
            choice_int = int(choice)
            if 1 <= choice_int <= len(examples):
                name, func = examples[choice_int - 1]
                print(f"\n🔄 Running: {name}")
                func()
            else:
                print("❌ Invalid choice")
        except ValueError:
            print("❌ Please enter a number")
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == '__main__':
    main()
