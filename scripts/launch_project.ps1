param(
    [string]$Mode = "mock",
    [string]$DataDir = "data/mock_problem_b",
    [double]$SampleRatio = 1.0,
    [int]$Epochs = 5,
    [int]$Patience = 2
)

$python = ".venv\\Scripts\\python.exe"
if (-not (Test-Path $python)) {
    Write-Host ".venv not found. Run: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

& $python q1new.py --dataset-mode $Mode --data-dir $DataDir --sample-ratio $SampleRatio --epochs $Epochs --patience $Patience
