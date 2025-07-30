#!/bin/bash

echo "🔑 GitHub Token Setup Helper"
echo "============================"
echo ""
echo "1. Set your token (replace YOUR_TOKEN_HERE with your actual token):"
echo '   export GITHUB_TOKEN="YOUR_TOKEN_HERE"'
echo ""
echo "2. Test the setup:"
echo "   python3 test_github_setup.py --test"
echo ""
echo "3. Run a quick simulation:"
echo "   python3 run_github_action.py --N 8 --T 50 --circuit-realizations 2 --L 2"
echo ""
echo "Current token status:"
if [ -z "$GITHUB_TOKEN" ]; then
    echo "   ❌ GITHUB_TOKEN not set"
else
    echo "   ✅ GITHUB_TOKEN is set (length: ${#GITHUB_TOKEN})"
fi
