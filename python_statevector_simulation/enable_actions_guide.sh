#!/bin/bash

echo "🎯 GitHub Actions Enablement Guide"
echo "=================================="
echo ""

echo "✅ Workflow file successfully pushed to GitHub!"
echo "   Repository: alessum/random_pauli"
echo "   File: .github/workflows/executor.yml"
echo ""

echo "📝 To enable GitHub Actions (required one-time setup):"
echo "1. Open your browser and visit:"
echo "   https://github.com/alessum/random_pauli"
echo ""
echo "2. Click the 'Actions' tab at the top"
echo ""
echo "3. If you see a message like:"
echo "   'Workflows aren't being run on this forked repository'"
echo "   or 'Actions are disabled on this repository'"
echo "   → Click 'I understand my workflows, go ahead and enable them'"
echo ""
echo "4. You should then see:"
echo "   - 'Parallel Simulations' workflow listed"
echo "   - Green 'Set up this workflow' or 'Run workflow' button"
echo ""

echo "🧪 After enabling, test with these commands:"
echo ""
echo "# Check if workflows are now visible:"
echo "python3 setup_github_config.py --list-workflows"
echo ""
echo "# Run a quick test simulation:"
echo "python3 run_github_action.py --N 8 --T 50 --circuit-realizations 2 --L 2"
echo ""

echo "🔍 Current status check:"
echo ""

# Check if token is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GITHUB_TOKEN not set"
else
    echo "✅ GITHUB_TOKEN is set"
fi

# Check if workflow file exists locally
if [ -f "../.github/workflows/executor.yml" ]; then
    echo "✅ Workflow file exists locally"
else
    echo "❌ Workflow file missing locally"
fi

# Test API access
echo ""
echo "Testing GitHub API access..."
python3 -c "
import requests
import os

token = os.getenv('GITHUB_TOKEN')
if not token:
    print('❌ No token available for API test')
    exit()

headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'}

# Test file exists on GitHub
url = 'https://api.github.com/repos/alessum/random_pauli/contents/.github/workflows/executor.yml'
try:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print('✅ Workflow file confirmed on GitHub')
    else:
        print(f'❌ Workflow file not found on GitHub (status: {response.status_code})')
except Exception as e:
    print(f'❌ API test failed: {e}')

# Test actions API
url = 'https://api.github.com/repos/alessum/random_pauli/actions/workflows'
try:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        workflows = response.json().get('workflows', [])
        if workflows:
            print(f'✅ GitHub Actions enabled ({len(workflows)} workflows found)')
        else:
            print('⚠️  GitHub Actions API accessible but no workflows found')
            print('   → Actions may need to be manually enabled in the GitHub web interface')
    else:
        print(f'❌ Actions API failed (status: {response.status_code})')
except Exception as e:
    print(f'❌ Actions API test failed: {e}')
"

echo ""
echo "🎯 Next steps:"
echo "1. Visit the GitHub repository in your browser"
echo "2. Enable Actions in the Actions tab"
echo "3. Run the test commands above"
echo "4. If successful, you can run larger simulations!"
