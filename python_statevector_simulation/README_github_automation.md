# GitHub Actions Automation for Quantum Simulations

This directory contains tools to automate and monitor quantum simulation workflows using GitHub Actions.

## Files

- **`run_github_action.py`** - Main script to trigger GitHub Actions workflows
- **`setup_github_config.py`** - Configuration and testing script
- **`example_usage.py`** - Examples and demonstrations
- **`single_run.py`** - Core simulation script (called by GitHub Actions)
- **`fetch.py`** - Script to download and organize simulation results

## Quick Start

### 1. Set up GitHub Token

First, create a GitHub personal access token:

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo` and `actions:write`
4. Copy the token

Set the token as an environment variable:
```bash
export GITHUB_TOKEN="your_token_here"
```

### 2. Test Your Setup

```bash
# Test token and list workflows
python3 setup_github_config.py

# Or test specific components
python3 setup_github_config.py --test-token --list-workflows
```

### 3. Run a Quick Test

```bash
# Small test run
python3 run_github_action.py --N 8 --T 100 --circuit-realizations 2 --L 2 --batch-size 2
```

### 4. Run Production Simulation

```bash
# Full simulation
python3 run_github_action.py --N 14 --T 1000 --circuit-realizations 10 --L 4 --batch-size 8
```

## Script Details

### `run_github_action.py`

Main script for triggering GitHub Actions workflows.

**Parameters:**
- `--N` - Number of qubits (required)
- `--T` - Time evolution steps (required)
- `--circuit-realizations` - Number of circuit realizations (required)
- `--L` - Grid resolution for parameter space (required)
- `--batch-size` - Points per parallel job (default: 5)
- `--monitor` - Monitor execution (true/false, default: true)
- `--timeout` - Monitoring timeout in minutes (default: 30)

**Repository settings:**
- `--owner` - GitHub username (default: alessum)
- `--repo` - Repository name (default: quera_proj)
- `--workflow` - Workflow file (default: executor.yml)

**Examples:**
```bash
# Basic usage
python3 run_github_action.py --N 14 --T 1000 --circuit-realizations 10 --L 3

# With custom repository
python3 run_github_action.py --owner myuser --repo myrepo --N 12 --T 500 --circuit-realizations 5 --L 2

# Fire and forget (no monitoring)
python3 run_github_action.py --N 10 --T 200 --circuit-realizations 3 --L 2 --monitor false

# Extended monitoring
python3 run_github_action.py --N 16 --T 2000 --circuit-realizations 20 --L 5 --timeout 60
```

### `setup_github_config.py`

Configuration and testing utilities.

**Options:**
- `--test-token` - Test GitHub token permissions
- `--list-workflows` - List available workflows
- `--test-dispatch` - Test workflow dispatch (dry run)
- `--save-config` - Save configuration to file

**Examples:**
```bash
# Test everything
python3 setup_github_config.py

# Test specific components
python3 setup_github_config.py --test-token
python3 setup_github_config.py --list-workflows
python3 setup_github_config.py --test-dispatch --N 12 --T 100 --circuit-realizations 2 --L 2
```

### `example_usage.py`

Interactive examples and demonstrations.

```bash
python3 example_usage.py
```

This script provides a menu with various examples:
1. Setup and Test - Verify configuration
2. Quick Test Run - Small simulation for testing
3. Production Run - Realistic parameters
4. Fire and Forget - Trigger without monitoring
5. Custom Repository - Different repo settings
6. Batch Runs - Multiple configurations

## Workflow Parameters

The GitHub Actions workflow accepts these parameters:

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| N | Number of qubits | 14 | 16 |
| T | Time evolution steps | 1000 | 2000 |
| circuit_realizations | Circuit realizations | 10 | 20 |
| L | Grid resolution (L×L) | 3 | 4 |
| batch_size | Points per job | 5 | 8 |

**Total jobs calculation:**
- Total points = `circuit_realizations × L × L`
- Number of parallel jobs = `ceil(total_points / batch_size)`

**Examples:**
- N=14, T=1000, cr=10, L=3: 90 points → 18 jobs (batch_size=5)
- N=16, T=2000, cr=20, L=4: 320 points → 40 jobs (batch_size=8)

## Output Structure

Results are organized as:
```
results/
├── magic/N{N}/T{T}/Jx{Jx}/Jz{Jz}/cr{cr}.npz
└── entanglement/N{N}/T{T}/Jx{Jx}/Jz{Jz}/cr{cr}.npz
```

**Example:**
```
results/magic/N14/T1000/Jx0.5/Jz1.2/cr7.npz
```

## Monitoring and Results

### Real-time Monitoring

When `--monitor true` (default), the script will:
- Show workflow status every 30 seconds
- Display creation time and GitHub URL
- Report completion status (success/failure)

### Downloading Results

After workflow completion, use `fetch.py` to download results:

```bash
python3 fetch.py --help
```

### GitHub Actions UI

You can also monitor workflows at:
```
https://github.com/{owner}/{repo}/actions
```

## Troubleshooting

### Common Issues

1. **Token permissions**
   ```
   ❌ Actions access failed: 403
   ```
   Solution: Ensure token has `repo` and `actions:write` scopes

2. **Repository not found**
   ```
   ❌ Repository owner/repo not found or no access
   ```
   Solution: Check repository name and token permissions

3. **Workflow not found**
   ```
   ❌ Workflow 'executor.yml' not found
   ```
   Solution: Verify workflow file exists in `.github/workflows/`

4. **Rate limiting**
   ```
   ❌ Error triggering workflow: 403
   ```
   Solution: Wait and retry, or check API rate limits

### Debug Tips

1. **Test token first:**
   ```bash
   python3 setup_github_config.py --test-token
   ```

2. **List available workflows:**
   ```bash
   python3 setup_github_config.py --list-workflows
   ```

3. **Run with dry run:**
   ```bash
   python3 setup_github_config.py --test-dispatch --N 8 --T 50 --circuit-realizations 1 --L 1
   ```

4. **Check workflow manually:**
   - Go to GitHub Actions tab
   - Look for recent workflow runs
   - Check logs for detailed error messages

### Environment Variables

```bash
# Required
export GITHUB_TOKEN="your_token_here"

# Optional (for custom settings)
export GITHUB_OWNER="your_username"
export GITHUB_REPO="your_repository"
```

## Best Practices

1. **Start small:** Test with small N and T values first
2. **Monitor resources:** Large simulations use significant compute time
3. **Batch appropriately:** Balance between job overhead and parallelism
4. **Check limits:** Be aware of GitHub Actions usage limits
5. **Save configurations:** Use `--save-config` for repeated setups

## Integration Examples

### Shell Script Integration

```bash
#!/bin/bash
# run_simulation_batch.sh

export GITHUB_TOKEN="your_token"

# Run multiple configurations
for N in 12 14 16; do
    for T in 500 1000 2000; do
        echo "Running N=$N, T=$T"
        python3 run_github_action.py \
            --N $N --T $T \
            --circuit-realizations 10 \
            --L 3 \
            --monitor false
        sleep 10  # Avoid rate limiting
    done
done
```

### Python Integration

```python
import subprocess
import time

configs = [
    {"N": 12, "T": 500, "cr": 5, "L": 2},
    {"N": 14, "T": 1000, "cr": 10, "L": 3},
    {"N": 16, "T": 2000, "cr": 15, "L": 4},
]

for config in configs:
    cmd = [
        "python3", "run_github_action.py",
        "--N", str(config["N"]),
        "--T", str(config["T"]),
        "--circuit-realizations", str(config["cr"]),
        "--L", str(config["L"]),
        "--monitor", "false"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Started: N={config['N']}, T={config['T']}")
    else:
        print(f"❌ Failed: N={config['N']}, T={config['T']}")
    
    time.sleep(10)  # Rate limiting
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review GitHub Actions logs
3. Test with smaller parameters first
4. Verify token permissions and repository access
